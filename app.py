# from flask import Flask, render_template, request, redirect, url_for, session, flash
# from werkzeug.security import generate_password_hash, check_password_hash
# import sqlite3

# app = Flask(__name__)
# app.secret_key = 'bus'

# # Database setup
# def init_db():
#     conn = sqlite3.connect('database.db')
#     conn.execute('''
#     CREATE TABLE IF NOT EXISTS users (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         username TEXT UNIQUE,
#         password TEXT,
#         is_admin BOOLEAN DEFAULT 0
#     )
#     ''')
#     conn.execute('CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, time TEXT, seat TEXT)')
#     conn.execute('CREATE TABLE IF NOT EXISTS seats (id INTEGER PRIMARY KEY AUTOINCREMENT, seat_number TEXT UNIQUE, is_available BOOLEAN)')
#     conn.close()


# # Home page
# @app.route('/')
# def index():
#     return render_template('index.html')

import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def init_db():
    conn = sqlite3.connect('database.db')

    # Users table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        contact_details TEXT,
        preferences TEXT,
        is_admin BOOLEAN DEFAULT 0
    )
    ''')

    # Routes table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departure_city TEXT,
        destination_city TEXT,
        route_duration TEXT
    )
    ''')

    # Buses table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS buses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bus_type TEXT,
        seating_capacity INTEGER,
        assigned_route INTEGER,
        FOREIGN KEY (assigned_route) REFERENCES routes(id)
    )
    ''')

    # Bookings table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        bus_id INTEGER,
        journey_date TEXT,
        seat_numbers TEXT,
        status TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (bus_id) REFERENCES buses(id)
    )
    ''')

    # Payments table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT,
        amount REAL,
        payment_status TEXT,
        timestamp TEXT,
        booking_id INTEGER,
        FOREIGN KEY (booking_id) REFERENCES bookings(id)
    )
    ''')

    # Feedback table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        feedback_text TEXT,
        rating INTEGER,
        timestamp TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    # Seats table for availability
    conn.execute('''
    CREATE TABLE IF NOT EXISTS seats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bus_id INTEGER,
        seat_number TEXT,
        is_available BOOLEAN,
        FOREIGN KEY (bus_id) REFERENCES buses(id)
    )
    ''')

    conn.close()

def populate_seats(bus_id, seating_capacity):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM seats WHERE bus_id = ?', (bus_id,))
    seat_count = cursor.fetchone()[0]

    if seat_count == 0:  # Populate only if the seats are not already populated
        seats = [(bus_id, f'Seat {i}', True) for i in range(1, seating_capacity + 1)]
        conn.executemany('INSERT INTO seats (bus_id, seat_number, is_available) VALUES (?, ?, ?)', seats)
        conn.commit()

    conn.close()

def initialize_data():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Fetch bus information
    cursor.execute('SELECT id, seating_capacity FROM buses')
    buses = cursor.fetchall()

    for bus_id, seating_capacity in buses:
        populate_seats(bus_id, seating_capacity)

    conn.close()


def add_is_admin_column():
    conn = sqlite3.connect('database.db')
    conn.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')
    conn.commit()
    conn.close()

### 2. Modified Routes

#### 2.1. Home Page (Route Selection)
@app.route('/', methods=['GET', 'POST'])
def index():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        departure_city = request.form['departure_city']
        destination_city = request.form['destination_city']
        journey_date = request.form['date']

        cursor.execute('''
            SELECT buses.id, buses.bus_type, buses.seating_capacity, routes.route_duration
            FROM buses
            JOIN routes ON buses.assigned_route = routes.id
            WHERE routes.departure_city = ? AND routes.destination_city = ?
        ''', (departure_city, destination_city))
        available_buses = cursor.fetchall()

        return render_template('select_bus.html', buses=available_buses, journey_date=journey_date)

    cursor.execute('SELECT DISTINCT departure_city FROM routes')
    departure_cities = cursor.fetchall()

    cursor.execute('SELECT DISTINCT destination_city FROM routes')
    destination_cities = cursor.fetchall()
    print('Departure Cities:', departure_cities)
    print('Destination Cities:', destination_cities)


    conn.close()
    return render_template('index.html', departure_cities=departure_cities, destination_cities=destination_cities)


@app.route('/select_bus/<int:bus_id>/<journey_date>', methods=['GET', 'POST'])
def select_bus(bus_id, journey_date):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        seat_numbers = request.form.getlist('seats')
        user_id = session.get('user_id')
        
        cursor.execute('''
            INSERT INTO bookings (user_id, bus_id, journey_date, seat_numbers, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, bus_id, journey_date, ','.join(seat_numbers), 'Pending'))
        conn.commit()

        # Mark seats as booked
        cursor.execute('''
            UPDATE seats SET is_available = 0 WHERE bus_id = ? AND seat_number IN ({})
        '''.format(','.join('?'*len(seat_numbers))), [bus_id] + seat_numbers)
        conn.commit()

        # Redirect to payment page
        return redirect(url_for('payment', booking_id=cursor.lastrowid))

    cursor.execute('SELECT seat_number, is_available FROM seats WHERE bus_id = ?', (bus_id,))
    seats = cursor.fetchall()
    conn.close()

    return render_template('seat_selection.html', seats=seats, bus_id=bus_id, journey_date=journey_date)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['is_admin'] = user[3]  # This ensures admin status is stored in the session
            flash('Login successful!')
            return redirect(url_for('index'))
        else:
            flash('Login failed. Please check your credentials.')

    return render_template('login.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        is_admin = 'is_admin' in request.form
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        conn = sqlite3.connect('database.db')
        try:
            conn.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)', (username, hashed_password, is_admin))
            conn.commit()
            flash('Registration successful! You can now log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose a different one.')
        finally:
            conn.close()

    return render_template('register.html')



@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('index'))

@app.route('/book', methods=['GET', 'POST'])
def book():
    if 'user_id' not in session:
        flash('Please log in to book a ticket.')
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        date = request.form['date']
        time = request.form['time']
        seat = request.form['seat']

        cursor = conn.cursor()
        cursor.execute('SELECT is_available FROM seats WHERE seat_number = ?', (seat,))
        seat_available = cursor.fetchone()

        if seat_available and seat_available[0]:
            conn.execute('INSERT INTO bookings (name, email, date, time, seat) VALUES (?, ?, ?, ?, ?)',
                         (name, email, date, time, seat))
            conn.execute('UPDATE seats SET is_available = 0 WHERE seat_number = ?', (seat,))
            conn.commit()
            flash('Booking successful!')
            return redirect(url_for('success'))
        else:
            flash('Sorry, the selected seat is not available.')
    
    seats = conn.execute('SELECT seat_number FROM seats WHERE is_available = 1').fetchall()
    conn.close()
    
    return render_template('book.html', seats=[seat[0] for seat in seats])

# def populate_seats():
#     conn = sqlite3.connect('database.db')
#     cursor = conn.execute('SELECT COUNT(*) FROM seats')
#     seat_count = cursor.fetchone()[0]

#     if seat_count == 0:  # Only populate if no seats exist
#         seats = [(f'Seat {i}', True) for i in range(1, 51)]
#         conn.executemany('INSERT INTO seats (seat_number, is_available) VALUES (?, ?)', seats)
#         conn.commit()

#     conn.close()


# Success page
@app.route('/success')
def success():
    return render_template('success.html')

# @app.route('/admin')
# def admin():
#     if 'user_id' not in session or not session.get('is_admin'):
#         flash('Admin access required.')
#         return redirect(url_for('login'))

#     conn = sqlite3.connect('database.db')
#     bookings = conn.execute('SELECT * FROM bookings').fetchall()
#     seats = conn.execute('SELECT * FROM seats').fetchall()
#     conn.close()

#     return render_template('admin.html', bookings=bookings, seats=seats)
@app.route('/admin')
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Admin access required.')
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM bookings')
    bookings = cursor.fetchall()

    cursor.execute('SELECT * FROM users WHERE is_admin = 0')
    users = cursor.fetchall()

    cursor.execute('SELECT * FROM routes')
    routes = cursor.fetchall()

    cursor.execute('SELECT * FROM buses')
    buses = cursor.fetchall()

    conn.close()

    return render_template('admin.html', bookings=bookings, users=users, routes=routes, buses=buses)


if __name__ == '__main__':
    init_db()
    initialize_data()
    app.run(debug=True)
