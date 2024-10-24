from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = 'super_secret_key'

def init_db():
    with sqlite3.connect('your_database.db') as conn:
        cursor = conn.cursor()
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                precio REAL NOT NULL,
                stock INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_producto INTEGER,
                cantidad INTEGER NOT NULL,
                total REAL NOT NULL,
                fecha TEXT NOT NULL,
                FOREIGN KEY(id_producto) REFERENCES productos(id)
            );

            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_cliente TEXT NOT NULL,
                direccion TEXT NOT NULL,
                total REAL NOT NULL,
                fecha TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pedido_productos (
                id_pedido INTEGER,
                id_producto INTEGER,
                cantidad INTEGER NOT NULL,
                FOREIGN KEY(id_pedido) REFERENCES pedidos(id),
                FOREIGN KEY(id_producto) REFERENCES productos(id)
            );
        ''')
        conn.commit()

# Función para enviar un correo cuando el stock es bajo
def enviar_correo_stock_bajo(productos_bajos):
    remitente = "entregasstock@gmail.com"  
    destinatario = "entregasstock@gmail.com"  
    contraseña = "cfwb edlw dcve dfba"  

    asunto = "Alerta de Stock Bajo en la Tienda"
    cuerpo = "Los siguientes productos tienen un stock bajo:\n\n"
    for producto in productos_bajos:
        cuerpo += f"- {producto[0]}: {producto[1]} unidades restantes\n"

    mensaje = MIMEMultipart()
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.attach(MIMEText(cuerpo, "plain"))

    try:
        servidor = smtplib.SMTP("smtp.gmail.com", 587)
        servidor.starttls()
        servidor.login(remitente, contraseña)
        servidor.sendmail(remitente, destinatario, mensaje.as_string())
        servidor.quit()
        print("Correo enviado correctamente")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")


def validar_correo(correo):
    return re.match(r'^[a-zA-Z0-9_.+-]+@gmail\.com$', correo)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if not validar_correo(email):
            flash('Por favor, ingresa un correo válido en formato @gmail.com.', 'error')
            return redirect(url_for('register'))

        with sqlite3.connect('your_database.db') as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO usuarios (email, password) VALUES (?, ?)", (email, password))
                conn.commit()
                flash('Usuario registrado con éxito!', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('El correo ya está en uso, elige otro.', 'error')
                return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        with sqlite3.connect('your_database.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM usuarios WHERE email = ? AND password = ?", (email, password))
            user = cursor.fetchone()

            if user:
                session['user_id'] = user[0]
                session['email'] = user[1]
                flash(f'Bienvenido, {email}!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Correo o contraseña incorrectos.', 'error')
                return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('email', None)
    flash('Sesión cerrada con éxito.', 'success')
    return redirect(url_for('login'))


@app.route('/productos', methods=['GET', 'POST'])
def productos():
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        precio = float(request.form['precio'])
        stock = int(request.form['stock'])

        with sqlite3.connect('your_database.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM productos WHERE nombre = ?", (nombre,))
            producto_existente = cursor.fetchone()

            if producto_existente:
                
                nuevo_stock = producto_existente[3] + stock
                cursor.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, producto_existente[0]))
                flash(f'Se han añadido {stock} unidades al stock de "{nombre}".', 'success')
            else:
                cursor.execute("INSERT INTO productos (nombre, precio, stock) VALUES (?, ?, ?)", (nombre, precio, stock))
                flash(f'Producto "{nombre}" añadido con éxito!', 'success')
            conn.commit()
        return redirect(url_for('productos'))

    with sqlite3.connect('your_database.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos")
        productos = cursor.fetchall()

    return render_template('productos.html', productos=productos)


@app.route('/productos/sugerencias', methods=['GET'])
def sugerencias_productos():
    termino = request.args.get('termino', '').strip()
    with sqlite3.connect('your_database.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nombre FROM productos WHERE nombre LIKE ?", (f'{termino}%',))
        sugerencias = [fila[0] for fila in cursor.fetchall()]
    return jsonify(sugerencias)


@app.route('/ventas', methods=['GET', 'POST'])
def ventas():
    if request.method == 'POST':
        productos = request.form.getlist('id_producto[]')
        cantidades = request.form.getlist('cantidad[]')
        total_venta = 0

        with sqlite3.connect('your_database.db') as conn:
            cursor = conn.cursor()
            for id_producto, cantidad in zip(productos, cantidades):
                cantidad = int(cantidad)
                cursor.execute("SELECT precio, stock FROM productos WHERE id = ?", (id_producto,))
                producto = cursor.fetchone()

                if producto and producto[1] >= cantidad:
                    total = producto[0] * cantidad
                    total_venta += total
                    cursor.execute("INSERT INTO ventas (id_producto, cantidad, total, fecha) VALUES (?, ?, ?, DATE('now'))", (id_producto, cantidad, total))
                    cursor.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, id_producto))
                else:
                    flash(f'Stock insuficiente para el producto con ID {id_producto}.', 'error')
                    return redirect(url_for('ventas'))
            conn.commit()
            flash('Venta registrada con éxito!', 'success')

        return redirect(url_for('ventas'))

    with sqlite3.connect('your_database.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos")
        productos = cursor.fetchall()

       
        cursor.execute("SELECT v.id, p.nombre, v.cantidad, v.total, v.fecha FROM ventas v JOIN productos p ON v.id_producto = p.id ORDER BY v.fecha DESC")
        ventas_recientes = cursor.fetchall()

        
        cursor.execute("SELECT SUM(total) FROM ventas")
        total_ventas_ventas = cursor.fetchone()[0] or 0

        
        cursor.execute("SELECT SUM(total) FROM pedidos")
        total_ventas_pedidos = cursor.fetchone()[0] or 0

        
        total_ventas = total_ventas_ventas + total_ventas_pedidos

    
    cursor.execute("SELECT nombre, stock FROM productos WHERE stock < 10")
    productos_bajos = cursor.fetchall()

    
    if productos_bajos:
        enviar_correo_stock_bajo(productos_bajos)

    return render_template('ventas.html', productos=productos, ventas=ventas_recientes, total_ventas=total_ventas, productos_bajos=productos_bajos)


@app.route('/pedidos', methods=['GET', 'POST'])
def pedidos():
    if request.method == 'POST':
        nombre_cliente = request.form['nombre_cliente'].strip()
        direccion = request.form['direccion'].strip()
        productos = request.form.getlist('productos[]')
        cantidades = request.form.getlist('cantidades[]')
        total_pedido = 0

        with sqlite3.connect('your_database.db') as conn:
            cursor = conn.cursor()

           
            cursor.execute("INSERT INTO pedidos (nombre_cliente, direccion, total, fecha) VALUES (?, ?, 0, DATE('now'))", (nombre_cliente, direccion))
            id_pedido = cursor.lastrowid

           
            for id_producto, cantidad in zip(productos, cantidades):
                cantidad = int(cantidad)
                cursor.execute("SELECT precio, stock FROM productos WHERE id = ?", (id_producto,))
                producto = cursor.fetchone()
                precio = producto[0]
                nuevo_stock = producto[1] - cantidad

                if nuevo_stock >= 0:
                    total_producto = precio * cantidad
                    total_pedido += total_producto
                    cursor.execute("INSERT INTO pedido_productos (id_pedido, id_producto, cantidad) VALUES (?, ?, ?)", (id_pedido, id_producto, cantidad))
                    cursor.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, id_producto))
                else:
                    flash(f'Stock insuficiente para {producto[1]}, no se puede añadir al pedido.', 'error')
                    return redirect(url_for('pedidos'))

            
            cursor.execute("UPDATE pedidos SET total = ? WHERE id = ?", (total_pedido, id_pedido))
            conn.commit()

            flash('Pedido registrado con éxito!', 'success')

        return redirect(url_for('pedidos'))

    with sqlite3.connect('your_database.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos")
        productos = cursor.fetchall()

        cursor.execute("SELECT * FROM pedidos ORDER BY fecha DESC")
        pedidos = cursor.fetchall()

        
        cursor.execute("SELECT SUM(total) FROM ventas")
        total_ventas_ventas = cursor.fetchone()[0] or 0

        
        cursor.execute("SELECT SUM(total) FROM pedidos")
        total_ventas_pedidos = cursor.fetchone()[0] or 0

        
        total_ventas = total_ventas_ventas + total_ventas_pedidos

    return render_template('pedidos.html', productos=productos, pedidos=pedidos, total_ventas=total_ventas)

if __name__ == '__main__':
    init_db()  
    app.run(debug=True)
