import yfinance as yf
from models import db, Asset
from datetime import datetime

def update_asset_prices(tickers=None):
    if tickers is None:
        assets = Asset.query.all()
        tickers = [a.ticker for a in assets]
    if not tickers:
        return
    data = yf.Tickers(' '.join(tickers))
    for t in tickers:
        try:
            hist = data.tickers[t].history(period='1d')
            if not hist.empty:
                last_price = float(hist['Close'][-1])
            else:
                last_price = float(data.tickers[t].info.get('previousClose', 0.0))
        except Exception as e:
            print('Error con', t, e)
            last_price = 0
        asset = Asset.query.filter_by(ticker=t).first()
        if asset:
            asset.last_price = last_price
            asset.updated_at = datetime.utcnow()
        db.session.commit()