from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User, Asset, Operation, Holding
from finance_fetch import update_asset_prices
import matplotlib

matplotlib.use('Agg')  # Backend without GUI for server
import matplotlib.pyplot as plt
import io, base64
import yfinance as yf

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.before_request
def setup():
    if not hasattr(app, 'setup_done'):
        with app.app_context():
            db.create_all()
            tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'JPM', 'BAC',
                       'GS', 'MS', 'V', 'MA', 'NVDA', 'META', 'IBM', 'ORCL']
            for t in tickers:
                if not Asset.query.filter_by(ticker=t).first():
                    db.session.add(Asset(ticker=t, name=t))
            db.session.commit()
            update_asset_prices(tickers)
        app.setup_done = True


@app.route('/')
def index():
    assets = Asset.query.all()
    return render_template('index.html', assets=assets)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        pwd = request.form['password']

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))

        user = User(name=name, email=email, password_hash=generate_password_hash(pwd))
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully! Login to start', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        pwd = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, pwd):
            login_user(user)
            flash(f'Welcome {user.name}!', 'success')
            return redirect(url_for('dashboard'))

        flash('Incorrect email or password', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Session closed successfully', 'success')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    assets = Asset.query.all()
    holdings = Holding.query.filter_by(user_id=current_user.id).all()

    portfolio_value = sum([
        (Asset.query.get(h.asset_id).last_price or 0) * h.quantity
        for h in holdings
    ])

    return render_template('dashboard.html',
                           assets=assets,
                           holdings=holdings,
                           cash=current_user.cash,
                           total_value=portfolio_value)


@app.route('/asset/<ticker>', methods=['GET', 'POST'])
@login_required
def asset_view(ticker):
    asset = Asset.query.filter_by(ticker=ticker).first_or_404()

    if request.method == 'POST':
        op_type = request.form['op_type']
        qty = float(request.form['quantity'])
        price = asset.last_price or 0

        if price == 0:
            flash('Cannot trade: price not available', 'danger')
            return redirect(url_for('asset_view', ticker=ticker))

        if op_type == 'buy':
            cost = qty * price
            if current_user.cash < cost:
                flash(f'Insufficient funds. You need €{cost:.2f}, you have €{current_user.cash:.2f}', 'danger')
            else:
                current_user.cash -= cost
                op = Operation(user_id=current_user.id, asset_id=asset.id,
                               type='buy', quantity=qty, price=price)
                db.session.add(op)

                h = Holding.query.filter_by(user_id=current_user.id, asset_id=asset.id).first()
                if not h:
                    db.session.add(Holding(user_id=current_user.id, asset_id=asset.id,
                                           quantity=qty, avg_price=price))
                else:
                    prev_val = h.quantity * h.avg_price
                    h.quantity += qty
                    h.avg_price = (prev_val + cost) / h.quantity

                db.session.commit()
                flash(f'✅ Purchase successful: {qty} shares of {ticker} for €{cost:.2f}', 'success')

        else:  # sell
            h = Holding.query.filter_by(user_id=current_user.id, asset_id=asset.id).first()
            if not h or h.quantity < qty:
                available = h.quantity if h else 0
                flash(f'Not enough shares. Available: {available}', 'danger')
            else:
                revenue = qty * price
                current_user.cash += revenue
                op = Operation(user_id=current_user.id, asset_id=asset.id,
                               type='sell', quantity=qty, price=price)
                h.quantity -= qty

                if h.quantity == 0:
                    db.session.delete(h)

                db.session.add(op)
                db.session.commit()
                flash(f'✅ Sale successful: {qty} shares of {ticker} for €{revenue:.2f}', 'success')

        return redirect(url_for('asset_view', ticker=ticker))


    hist = yf.Ticker(ticker).history(period='1mo')
    img = None

    if not hist.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(hist.index, hist['Close'], linewidth=2, color='#F43F5E')
        ax.set_title(f'{ticker} - Last Month', fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price (€)')
        ax.grid(True, alpha=0.3)

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img = base64.b64encode(buf.read()).decode('ascii')
        plt.close(fig)

    return render_template('asset.html', asset=asset, img=img)


@app.route('/portfolio')
@login_required
def portfolio():
    holdings = Holding.query.filter_by(user_id=current_user.id).all()
    data = []
    total = 0

    for h in holdings:
        a = Asset.query.get(h.asset_id)
        val = (a.last_price or 0) * h.quantity
        total += val
        data.append({
            'ticker': a.ticker,
            'qty': h.quantity,
            'avg_price': h.avg_price,
            'last_price': a.last_price,
            'value': val
        })

    return render_template('portfolio.html',
                           holdings=data,
                           cash=current_user.cash,
                           total_value=total)


if __name__ == '__main__':
    app.run(debug=True)