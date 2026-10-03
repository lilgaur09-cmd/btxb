from __future__ import annotations

import base64
import json
from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit.components.v1 as components
from plotly.offline import get_plotlyjs_version
from plotly.subplots import make_subplots

from crypto_analysis import normalize_coinbase_symbol


def render_realtime_chart(
    symbol: str,
    interval: str,
    candles: List[Dict[str, Any]],
    live_price: float,
    summary: Dict[str, Any],
    follow_live: bool,
    stream: bool = True,
    price_prefix: str = "$",
) -> None:
    frame = pd.DataFrame(candles)
    frame["time"] = pd.to_datetime(frame["time"], unit="ms", utc=True)
    frame["ema_9"] = frame["close"].ewm(span=9, adjust=False).mean()
    frame["ema_21"] = frame["close"].ewm(span=21, adjust=False).mean()
    price_delta = frame["close"].diff()
    average_gain = price_delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    average_loss = -price_delta.clip(upper=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    relative_strength = average_gain / average_loss.replace(0, float("nan"))
    frame["rsi"] = (100 - 100 / (1 + relative_strength)).fillna(50)
    frame.loc[(average_loss == 0) & (average_gain > 0), "rsi"] = 100
    bar_colors = [
        "#16c784" if close >= open_price else "#ea3943"
        for open_price, close in zip(frame["open"], frame["close"])
    ]

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.68, 0.18, 0.14],
        subplot_titles=(f"{symbol} · {interval}", "Volume", "RSI 14"),
    )
    fig.add_trace(
        go.Candlestick(
            x=frame["time"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            increasing_line_color="#16c784",
            decreasing_line_color="#ea3943",
            increasing_fillcolor="#16c784",
            decreasing_fillcolor="#ea3943",
            name="Price",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=frame["time"], y=frame["ema_9"], name="EMA 9", line={"color": "#48bfe3", "width": 1.5}),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=frame["time"], y=frame["ema_21"], name="EMA 21", line={"color": "#f4a261", "width": 1.5}),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(x=frame["time"], y=frame["volume"], marker_color=bar_colors, name="Volume", showlegend=False),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=frame["time"], y=frame["rsi"], name="RSI 14", line={"color": "#c084fc", "width": 1.5}),
        row=3,
        col=1,
    )
    fig.add_hline(y=summary["support"], line_dash="dash", line_color="#9ecaff", line_width=1, row=1, col=1)
    fig.add_hline(y=summary["resistance"], line_dash="dash", line_color="#f4c430", line_width=1, row=1, col=1)
    fig.add_hline(y=live_price or summary["last_close"], line_dash="dot", line_color="#f3f4f6", line_width=1, row=1, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#ea3943", line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#16c784", line_width=1, row=3, col=1)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0b1220",
        plot_bgcolor="#0b1220",
        font={"color": "#e5e7eb"},
        height=900,
        margin={"l": 12, "r": 56, "t": 50, "b": 24},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "left", "x": 0},
        hovermode="x unified",
        transition={"duration": 0},
        uirevision=f"{symbol}-{interval}",
        xaxis_rangeslider_visible=False,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, rangeslider_visible=False)
    if follow_live:
        interval_seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}[interval]
        visible_start = frame["time"].iloc[max(0, len(frame) - 120)]
        visible_end = frame["time"].iloc[-1] + pd.Timedelta(seconds=interval_seconds)
        fig.update_xaxes(range=[visible_start, visible_end])
    fig.update_yaxes(showgrid=True, gridcolor="#1f2937", zeroline=False)
    fig.update_yaxes(range=[0, 100], row=3, col=1)

    seed = {
        "time": [value.isoformat() for value in frame["time"]],
        "open": frame["open"].astype(float).tolist(),
        "high": frame["high"].astype(float).tolist(),
        "low": frame["low"].astype(float).tolist(),
        "close": frame["close"].astype(float).tolist(),
        "volume": frame["volume"].astype(float).tolist(),
      "traded": (frame["volume"] > 0).tolist(),
    }
    settings = {
        "symbol": symbol,
        "stream": stream,
        "streamUrl": "wss://ws-feed.exchange.coinbase.com",
        "productId": normalize_coinbase_symbol(symbol) if stream else "",
        "intervalMs": {"1m": 60000, "5m": 300000, "15m": 900000, "1h": 3600000}[interval],
        "followLive": follow_live,
        "pricePrefix": price_prefix,
    }
    initial_price = live_price if live_price and live_price > 0 else float(frame["close"].iloc[-1])
    settings["initialPrice"] = initial_price
    figure_payload = base64.b64encode(fig.to_json().encode("utf-8")).decode("ascii")
    seed_payload = base64.b64encode(json.dumps(seed, allow_nan=False).encode("utf-8")).decode("ascii")
    settings_payload = base64.b64encode(json.dumps(settings).encode("utf-8")).decode("ascii")
    plotly_version = get_plotlyjs_version()

    components.html(
        f"""
        <div id="chart-status" style="color:#16c784;font:12px sans-serif;padding:4px 8px">Connecting to markets...</div>
        <div id="live-price" style="color:#e5e7eb;font:24px sans-serif;padding:4px 8px">{price_prefix}{initial_price:,.2f}</div>
        <div id="live-chart" style="width:100%;height:900px"></div>
        <script src="https://cdn.plot.ly/plotly-{plotly_version}.min.js"></script>
        <script>
          const chartFigure = JSON.parse(atob("{figure_payload}"));
          const candleData = JSON.parse(atob("{seed_payload}"));
          const settings = JSON.parse(atob("{settings_payload}"));
          const chartStatus = document.getElementById("chart-status");
          if (!settings.stream) {{ chartStatus.style.display = "none"; }}
          const livePrice = document.getElementById("live-price");
          const chartElement = document.getElementById("live-chart");
          let reconnectDelay = 1000;
          let pendingTrades = [];
          let frameQueued = false;
          let updateInFlight = false;

          function exponential(values, period) {{
            if (!values.length) return [];
            const factor = 2 / (period + 1);
            let value = values[0];
            return values.map((item, index) => {{
              if (index > 0) value += factor * (item - value);
              return value;
            }});
          }}

          function rsiSeries(values) {{
            return values.map((_, index) => {{
              if (index < 14) return 50;
              let gains = 0;
              let losses = 0;
              for (let position = index - 13; position <= index; position++) {{
                const change = values[position] - values[position - 1];
                gains += Math.max(change, 0);
                losses += Math.max(-change, 0);
              }}
              if (losses === 0) return 100;
              const strength = (gains / 14) / (losses / 14);
              return 100 - 100 / (1 + strength);
            }});
          }}

          function appendEmptyCandle(time) {{
            const previousClose = candleData.close[candleData.close.length - 1];
            candleData.time.push(new Date(time).toISOString());
            candleData.open.push(previousClose);
            candleData.high.push(previousClose);
            candleData.low.push(previousClose);
            candleData.close.push(previousClose);
            candleData.volume.push(0);
            candleData.traded.push(false);
            if (candleData.time.length > 180) {{
              for (const values of Object.values(candleData)) values.shift();
            }}
          }}

          function applyTrade(trade) {{
            const price = Number(trade.p);
            const quantity = Number(trade.q);
            const candleStart = Math.floor(Number(trade.T) / settings.intervalMs) * settings.intervalMs;
            let lastStart = Date.parse(candleData.time[candleData.time.length - 1]);
            if (candleStart < lastStart) return;
            while (lastStart < candleStart) {{
              lastStart += settings.intervalMs;
              appendEmptyCandle(lastStart);
            }}

            const index = candleData.time.length - 1;
            if (!candleData.traded[index]) {{
              candleData.open[index] = price;
              candleData.high[index] = price;
              candleData.low[index] = price;
              candleData.close[index] = price;
              candleData.volume[index] = quantity;
              candleData.traded[index] = true;
            }} else {{
              candleData.high[index] = Math.max(candleData.high[index], price);
              candleData.low[index] = Math.min(candleData.low[index], price);
              candleData.close[index] = price;
              candleData.volume[index] += quantity;
            }}
            livePrice.textContent = settings.pricePrefix + price.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:8}});
          }}

          async function flushTrades() {{
            frameQueued = false;
            if (updateInFlight) {{
              scheduleChartUpdate();
              return;
            }}
            updateInFlight = true;
            const batch = pendingTrades;
            pendingTrades = [];
            for (const trade of batch) applyTrade(trade);

            const closes = candleData.close;
            const colors = closes.map((close, index) => close >= candleData.open[index] ? "#16c784" : "#ea3943");
            const support = Math.min(...candleData.low.slice(-20));
            const resistance = Math.max(...candleData.high.slice(-20));
            await Promise.all([
              Plotly.restyle(chartElement, {{x:[candleData.time],open:[candleData.open],high:[candleData.high],low:[candleData.low],close:[closes]}}, [0]),
              Plotly.restyle(chartElement, {{x:[candleData.time],y:[exponential(closes,9)]}}, [1]),
              Plotly.restyle(chartElement, {{x:[candleData.time],y:[exponential(closes,21)]}}, [2]),
              Plotly.restyle(chartElement, {{x:[candleData.time],y:[candleData.volume],"marker.color":[colors]}}, [3]),
              Plotly.restyle(chartElement, {{x:[candleData.time],y:[rsiSeries(closes)]}}, [4]),
              Plotly.relayout(chartElement, {{
                "shapes[0].y0":support,"shapes[0].y1":support,
                "shapes[1].y0":resistance,"shapes[1].y1":resistance,
                "shapes[2].y0":closes[closes.length - 1],"shapes[2].y1":closes[closes.length - 1]
              }})
            ]);
            if (settings.followLive) {{
              const end = Date.parse(candleData.time[candleData.time.length - 1]) + settings.intervalMs;
              const start = Date.parse(candleData.time[Math.max(0, candleData.time.length - 120)]);
              const range = [new Date(start).toISOString(), new Date(end).toISOString()];
              await Plotly.relayout(chartElement, {{"xaxis.range":range,"xaxis2.range":range,"xaxis3.range":range}});
            }}
            updateInFlight = false;
            if (pendingTrades.length) scheduleChartUpdate();
          }}

          function scheduleChartUpdate() {{
            if (!frameQueued) {{
              frameQueued = true;
              requestAnimationFrame(flushTrades);
            }}
          }}

          function connect() {{
            chartStatus.style.display = "block";
            chartStatus.textContent = "Connecting to markets...";
            const socket = new WebSocket(settings.streamUrl);
            socket.onopen = () => {{
              reconnectDelay = 1000;
              socket.send(JSON.stringify({{type:"subscribe",product_ids:[settings.productId],channels:["ticker"]}}));
              chartStatus.style.display = "none";
            }};
            socket.onmessage = event => {{
              const message = JSON.parse(event.data);
              if (message.type === "ticker" && message.product_id === settings.productId) {{
                pendingTrades.push({{p:message.price,q:message.last_size || "0",T:Date.parse(message.time)}});
                scheduleChartUpdate();
              }}
            }};
            socket.onclose = () => {{
              chartStatus.style.display = "block";
              chartStatus.textContent = "Reconnecting to markets...";
              setTimeout(connect, reconnectDelay);
              reconnectDelay = Math.min(reconnectDelay * 2, 30000);
            }};
          }}

          Plotly.newPlot(chartElement, chartFigure.data, chartFigure.layout, {{responsive:true,scrollZoom:true,displaylogo:false}})
            .then(() => {{ if (settings.stream) connect(); }})
            .catch(error => {{ chartStatus.textContent = `Chart load failed: ${{error.message}}`; }});
        </script>
        """,
        height=940,
        scrolling=False,
    )
