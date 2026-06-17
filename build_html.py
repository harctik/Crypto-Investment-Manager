import json

m1 = open('m1.txt', encoding='utf-8').read().replace('<', '&lt;').replace('>', '&gt;')
m2 = open('m2.txt', encoding='utf-8').read().replace('<', '&lt;').replace('>', '&gt;')
m3 = open('m3.txt', encoding='utf-8').read().replace('<', '&lt;').replace('>', '&gt;')
m4 = open('m4.txt', encoding='utf-8').read().replace('<', '&lt;').replace('>', '&gt;')
m5 = open('m5.txt', encoding='utf-8').read().replace('<', '&lt;').replace('>', '&gt;')

html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>CryptoManager - HTML Screenshots</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #f0f2f5;
            color: #333;
            padding: 40px 20px;
            max-width: 1000px;
            margin: 0 auto;
        }}
        h2 {{
            color: #1a1a1a;
            margin-top: 40px;
            border-bottom: 2px solid #ddd;
            padding-bottom: 10px;
        }}
        .terminal-window {{
            background: #1e1e1e;
            border-radius: 8px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            margin-bottom: 30px;
            overflow: hidden;
        }}
        .terminal-header {{
            background: #323233;
            padding: 10px;
            display: flex;
            align-items: center;
        }}
        .terminal-buttons {{
            display: flex;
            gap: 8px;
        }}
        .terminal-button {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
        .close {{ background: #ff5f56; }}
        .minimize {{ background: #ffbd2e; }}
        .maximize {{ background: #27c93f; }}
        .terminal-title {{
            color: #ccc;
            font-size: 13px;
            flex-grow: 1;
            text-align: center;
            font-family: monospace;
        }}
        .terminal-body {{
            padding: 20px;
            color: #d4d4d4;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.5;
            white-space: pre-wrap;
            overflow-x: auto;
        }}
        .browser-window {{
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
            margin-bottom: 30px;
            overflow: hidden;
            border: 1px solid #ddd;
        }}
        .browser-header {{
            background: #f1f3f4;
            padding: 10px;
            display: flex;
            align-items: center;
            border-bottom: 1px solid #ddd;
        }}
        .browser-address-bar {{
            background: #fff;
            border-radius: 20px;
            padding: 5px 15px;
            color: #333;
            font-size: 13px;
            flex-grow: 1;
            margin: 0 20px;
            border: 1px solid #ccc;
            font-family: sans-serif;
        }}
        .browser-body {{
            padding: 0;
        }}
        .dashboard-mockup {{
            padding: 30px;
            background: #111827;
            color: white;
            font-family: sans-serif;
        }}
        .dash-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 1px solid #374151;
            padding-bottom: 15px;
        }}
        .dash-table {{
            width: 100%;
            border-collapse: collapse;
            background: #1f2937;
            border-radius: 8px;
            overflow: hidden;
        }}
        .dash-table th, .dash-table td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #374151;
        }}
        .dash-table th {{
            background: #374151;
            color: #9ca3af;
            font-size: 12px;
            text-transform: uppercase;
        }}
        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge-green {{ background: rgba(16, 185, 129, 0.2); color: #10b981; }}
        .badge-red {{ background: rgba(239, 68, 68, 0.2); color: #ef4444; }}
        .badge-yellow {{ background: rgba(245, 158, 11, 0.2); color: #f59e0b; }}
    </style>
</head>
<body>
    <h1>CryptoManager Report - HTML Screenshots</h1>
    <p>Use this page to capture exact high-quality HTML/CSS screenshots of the terminal outputs and web dashboard for your documentation.</p>

    <h2>7.1 Milestone 1 — Database Initialization and Live Price Fetch</h2>
    <div class="terminal-window">
        <div class="terminal-header">
            <div class="terminal-buttons">
                <div class="terminal-button close"></div>
                <div class="terminal-button minimize"></div>
                <div class="terminal-button maximize"></div>
            </div>
            <div class="terminal-title">bash - python main.py --milestone=1</div>
        </div>
        <div class="terminal-body">{m1}</div>
    </div>

    <h2>7.2 Milestone 2 — Monte Carlo Mix Calculator Results</h2>
    <div class="terminal-window">
        <div class="terminal-header">
            <div class="terminal-buttons">
                <div class="terminal-button close"></div>
                <div class="terminal-button minimize"></div>
                <div class="terminal-button maximize"></div>
            </div>
            <div class="terminal-title">bash - python main.py --milestone=2</div>
        </div>
        <div class="terminal-body">{m2}</div>
    </div>

    <h2>7.3 Milestone 3 — Risk Checker Output and Alert System</h2>
    <div class="terminal-window">
        <div class="terminal-header">
            <div class="terminal-buttons">
                <div class="terminal-button close"></div>
                <div class="terminal-button minimize"></div>
                <div class="terminal-button maximize"></div>
            </div>
            <div class="terminal-title">bash - python main.py --milestone=3</div>
        </div>
        <div class="terminal-body">{m3}</div>
    </div>

    <h2>7.4 Milestone 4 — Portfolio Spreading Rules and Rebalancing</h2>
    <div class="terminal-window">
        <div class="terminal-header">
            <div class="terminal-buttons">
                <div class="terminal-button close"></div>
                <div class="terminal-button minimize"></div>
                <div class="terminal-button maximize"></div>
            </div>
            <div class="terminal-title">bash - python main.py --milestone=4</div>
        </div>
        <div class="terminal-body">{m4}</div>
    </div>

    <h2>7.5 Milestone 5 — Backtesting Results and Stress Test</h2>
    <div class="terminal-window">
        <div class="terminal-header">
            <div class="terminal-buttons">
                <div class="terminal-button close"></div>
                <div class="terminal-button minimize"></div>
                <div class="terminal-button maximize"></div>
            </div>
            <div class="terminal-title">bash - python main.py --milestone=5</div>
        </div>
        <div class="terminal-body">{m5}</div>
    </div>

    <h2>7.6 Flask Web Dashboard</h2>
    <div class="browser-window">
        <div class="browser-header">
            <div class="terminal-buttons">
                <div class="terminal-button close"></div>
                <div class="terminal-button minimize"></div>
                <div class="terminal-button maximize"></div>
            </div>
            <div class="browser-address-bar">&#128274; http://localhost:5000/dashboard</div>
        </div>
        <div class="browser-body">
            <div class="dashboard-mockup">
                <div class="dash-header">
                    <h2 style="margin: 0; color: white; border: none; padding-bottom: 0;">&#9889; CryptoManager Dashboard</h2>
                    <div style="font-size: 20px;">Total Portfolio: <strong>$6,305.43</strong></div>
                </div>
                <table class="dash-table">
                    <thead>
                        <tr>
                            <th>Asset</th>
                            <th>Price</th>
                            <th>24h Change</th>
                            <th>Risk Tier</th>
                            <th>Signal</th>
                            <th>Portfolio Alloc</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>Bitcoin</strong> (BTC)</td>
                            <td>$81,027.00</td>
                            <td style="color: #10b981;">+1.24%</td>
                            <td><span class="badge badge-green">LOW RISK</span></td>
                            <td><span class="badge badge-green">BUY 🟢</span></td>
                            <td>64.25%</td>
                        </tr>
                        <tr>
                            <td><strong>Ethereum</strong> (ETH)</td>
                            <td>$2,329.37</td>
                            <td style="color: #ef4444;">-1.47%</td>
                            <td><span class="badge badge-yellow">MED RISK</span></td>
                            <td><span class="badge badge-yellow">HOLD 🟡</span></td>
                            <td>18.47%</td>
                        </tr>
                        <tr>
                            <td><strong>Binance Coin</strong> (BNB)</td>
                            <td>$646.69</td>
                            <td style="color: #10b981;">+1.89%</td>
                            <td><span class="badge badge-green">LOW RISK</span></td>
                            <td><span class="badge badge-green">BUY 🟢</span></td>
                            <td>10.26%</td>
                        </tr>
                        <tr>
                            <td><strong>Solana</strong> (SOL)</td>
                            <td>$88.54</td>
                            <td style="color: #10b981;">+1.41%</td>
                            <td><span class="badge badge-red">HIGH RISK</span></td>
                            <td><span class="badge badge-yellow">HOLD 🟡</span></td>
                            <td>7.02%</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""

with open('CryptoManager_Screenshots.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Generated CryptoManager_Screenshots.html successfully!')
