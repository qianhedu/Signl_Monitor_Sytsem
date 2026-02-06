import pandas as pd
import matplotlib.pyplot as plt
import io
import zipfile
import os

# Set font for Chinese characters - try common Windows Chinese fonts
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'SimSun']
plt.rcParams['axes.unicode_minus'] = False

def create_dkx_plot(df, symbol, symbol_name, signal_date=None):
    """Generate DKX plot image bytes"""
    plt.figure(figsize=(12, 6))
    
    # Plot data
    plt.plot(df.index, df['close'], label='Close', color='#333333', alpha=0.6)
    plt.plot(df.index, df['dkx'], label='DKX', color='#FF9800', linewidth=1.5)
    plt.plot(df.index, df['madkx'], label='MADKX', color='#2196F3', linewidth=1.5)
    
    # Highlight signal if provided
    if signal_date:
        try:
            signal_date = pd.to_datetime(signal_date)
            # Handle timezone matching
            if df.index.tz is not None and signal_date.tzinfo is None:
                signal_date = signal_date.tz_localize(df.index.tz)
            elif df.index.tz is None and signal_date.tzinfo is not None:
                signal_date = signal_date.tz_localize(None)
            
            # Find nearest index if exact match fails
            if signal_date in df.index:
                price = df.loc[signal_date, 'close']
                plt.scatter([signal_date], [price], color='red', s=100, zorder=5, label='Signal')
                
                # Add text annotation
                plt.annotate(f'Signal {signal_date.strftime("%Y-%m-%d")}', 
                             xy=(signal_date, price),
                             xytext=(10, 10), textcoords='offset points',
                             arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=.2"))
        except Exception as e:
            print(f"Plot annotation error: {e}")

    plt.title(f"{symbol_name} ({symbol}) DKX Trend")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    buf.seek(0)
    return buf.read()

def create_ma_plot(df, symbol, symbol_name, short_period, long_period, signal_date=None):
    """Generate MA plot image bytes"""
    plt.figure(figsize=(12, 6))
    
    # Plot data
    plt.plot(df.index, df['close'], label='Close', color='#333333', alpha=0.6)
    plt.plot(df.index, df['ma_short'], label=f'MA{short_period}', color='#FF9800', linewidth=1.5)
    plt.plot(df.index, df['ma_long'], label=f'MA{long_period}', color='#2196F3', linewidth=1.5)
    
    if signal_date:
        try:
            signal_date = pd.to_datetime(signal_date)
            # Handle timezone matching
            if df.index.tz is not None and signal_date.tzinfo is None:
                signal_date = signal_date.tz_localize(df.index.tz)
            elif df.index.tz is None and signal_date.tzinfo is not None:
                signal_date = signal_date.tz_localize(None)
                
            if signal_date in df.index:
                price = df.loc[signal_date, 'close']
                plt.scatter([signal_date], [price], color='red', s=100, zorder=5, label='Signal')
                
                # Add text annotation
                plt.annotate(f'Signal {signal_date.strftime("%Y-%m-%d")}', 
                             xy=(signal_date, price),
                             xytext=(10, 10), textcoords='offset points',
                             arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=.2"))
        except Exception as e:
            print(f"Plot annotation error: {e}")

    plt.title(f"{symbol_name} ({symbol}) MA Trend")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    buf.seek(0)
    return buf.read()

def create_export_zip(csv_content, charts_map, csv_filename="data.csv"):
    """
    Create a zip file containing CSV and charts
    charts_map: dict {filename: image_bytes}
    """
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add CSV
        # Add BOM for Excel compatibility
        if not csv_content.startswith('\ufeff'):
            csv_content = '\ufeff' + csv_content
        zip_file.writestr(csv_filename, csv_content)
        
        # Add Charts
        for filename, img_data in charts_map.items():
            zip_file.writestr(f"charts/{filename}", img_data)
            
    zip_buffer.seek(0)
    return zip_buffer
