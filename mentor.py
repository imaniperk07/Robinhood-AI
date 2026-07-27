from jarvis import ask_jarvis

MENTOR_SYSTEM_PROMPT = """You are Mentor, the investing teacher for this platform.

Your job is purely educational — teach investing fundamentals, technical analysis, fundamental
analysis, portfolio management, risk management, and financial terminology. You are not here to
recommend specific trades.

Rules:
- Always define any jargon before or as soon as you use it — never assume prior knowledge.
- Use simple, concrete analogies where they help.
- Keep answers focused on teaching the concept, not analyzing a specific stock, unless the user
  asks for a live example — in that case, use your tools to pull one and use it to illustrate the
  concept.
- Encourage curiosity. It's fine to end with a related question the user might want to explore next.
- Never tell the user to buy or sell, and never guarantee profits.
- If a tool returns an error or missing data, say so plainly instead of making something up.
"""


def ask_mentor(user_message: str, history: list[dict]) -> tuple[str, list[dict]]:
    return ask_jarvis(user_message, history, system_prompt=MENTOR_SYSTEM_PROMPT, agent="Mentor")


GLOSSARY = {
    "Technical Analysis": {
        "RSI (Relative Strength Index)": {
            "definition": "A 0-100 momentum gauge based on recent gains vs. losses. Above 70 is often "
                           "called 'overbought,' below 30 'oversold.'",
            "why_it_matters": "It's a rough read on whether a stock has moved too far, too fast in one "
                               "direction — not a guarantee it will reverse.",
        },
        "MACD (Moving Average Convergence Divergence)": {
            "definition": "Compares two moving averages (12-day and 26-day) to gauge momentum. When the "
                           "MACD line crosses above its signal line, it's often read as bullish; below, "
                           "bearish.",
            "why_it_matters": "Helps spot shifts in momentum earlier than price alone might show.",
        },
        "SMA (Simple Moving Average)": {
            "definition": "The average closing price over a set number of days (e.g. 20-day SMA = "
                           "average of the last 20 closes), smoothing out day-to-day noise.",
            "why_it_matters": "Price above its moving average is commonly read as an uptrend; below, a "
                               "downtrend.",
        },
        "EMA (Exponential Moving Average)": {
            "definition": "Like an SMA, but weights recent prices more heavily, so it reacts faster to "
                           "new information.",
            "why_it_matters": "Used inside MACD and by traders who want a quicker-reacting trend line "
                               "than a plain SMA.",
        },
        "Bollinger Bands": {
            "definition": "A band drawn above and below a moving average, sized by recent volatility. "
                           "Price near the upper band is 'stretched' up; near the lower band, 'stretched' "
                           "down.",
            "why_it_matters": "Gives a sense of whether a move is unusually large relative to the stock's "
                               "own recent behavior.",
        },
        "Support & Resistance": {
            "definition": "Support is a price level a stock has tended to bounce off; resistance is a "
                           "level it's tended to struggle to break above.",
            "why_it_matters": "These are historical patterns, not guarantees — but many traders watch "
                               "them because enough other traders do too.",
        },
        "Volume": {
            "definition": "The number of shares traded in a given period.",
            "why_it_matters": "A price move on unusually high volume is generally considered more "
                               "meaningful than the same move on light volume.",
        },
    },
    "Fundamental Analysis": {
        "P/E Ratio (Price-to-Earnings)": {
            "definition": "Share price divided by earnings per share — roughly, how many dollars "
                           "investors are paying for each dollar of annual profit.",
            "why_it_matters": "A rough valuation gauge. A high P/E can mean the market expects strong "
                               "future growth — or that the stock is simply expensive.",
        },
        "Revenue Growth": {
            "definition": "How much a company's total sales have grown, usually compared year-over-year.",
            "why_it_matters": "Sustained revenue growth is often a sign of a healthy, expanding business.",
        },
        "Earnings Growth": {
            "definition": "How much a company's profit has grown, usually compared year-over-year.",
            "why_it_matters": "Growing earnings faster than revenue can signal improving efficiency; "
                               "shrinking earnings despite revenue growth can signal rising costs.",
        },
        "Profit Margin": {
            "definition": "Net profit as a percentage of revenue — how much of every sales dollar "
                           "actually becomes profit.",
            "why_it_matters": "Higher margins generally mean more pricing power or efficiency than "
                               "competitors.",
        },
        "Return on Equity (ROE)": {
            "definition": "Net profit divided by shareholder equity — how efficiently a company turns "
                           "invested capital into profit.",
            "why_it_matters": "A consistently high ROE can indicate a well-run, capital-efficient "
                               "business.",
        },
        "Debt-to-Equity": {
            "definition": "Total debt divided by shareholder equity — how much a company relies on "
                           "borrowed money versus its own capital.",
            "why_it_matters": "Higher debt can amplify returns in good times but adds risk if earnings "
                               "fall or rates rise.",
        },
        "Free Cash Flow": {
            "definition": "Cash generated from operations, minus money spent maintaining/growing the "
                           "business.",
            "why_it_matters": "Positive free cash flow means a company can fund itself without "
                               "borrowing or issuing new stock.",
        },
        "Dividend Yield": {
            "definition": "Annual dividend payments divided by share price, shown as a percentage.",
            "why_it_matters": "Income-focused investors often weigh this alongside a company's ability "
                               "to sustain the payment.",
        },
    },
    "Portfolio Management": {
        "Diversification": {
            "definition": "Spreading investments across different companies, sectors, or asset types "
                           "instead of concentrating in a few.",
            "why_it_matters": "Reduces the impact any single holding's bad outcome has on your whole "
                               "portfolio.",
        },
        "Sector Allocation": {
            "definition": "How your portfolio's value is split across industries (tech, healthcare, "
                           "energy, etc.).",
            "why_it_matters": "Heavy concentration in one sector means your whole portfolio rises and "
                               "falls with that sector's fortunes.",
        },
        "Asset Allocation": {
            "definition": "How your money is split across broad asset classes — stocks, bonds, cash, "
                           "and so on.",
            "why_it_matters": "Usually the biggest single driver of a portfolio's long-term risk and "
                               "return profile.",
        },
        "Rebalancing": {
            "definition": "Periodically adjusting holdings back toward your target allocation as some "
                           "positions grow faster than others.",
            "why_it_matters": "Without it, winners can quietly grow into an outsized share of your "
                               "portfolio, raising your risk without you deciding that on purpose.",
        },
        "Position Sizing": {
            "definition": "How much of your portfolio you put into any single holding.",
            "why_it_matters": "Even a great idea can hurt you badly if it's sized too large relative to "
                               "the rest of your portfolio.",
        },
        "Dollar-Cost Averaging": {
            "definition": "Investing a fixed amount on a regular schedule, regardless of price.",
            "why_it_matters": "Smooths out the effect of buying at any single price point, removing the "
                               "pressure to 'time' the market.",
        },
    },
    "Risk Management": {
        "Risk Tolerance": {
            "definition": "How much loss or volatility you can handle — financially and emotionally — "
                           "without abandoning your plan.",
            "why_it_matters": "A strategy you can't stick with during a downturn isn't really a strategy.",
        },
        "Beta": {
            "definition": "A measure of how much a stock tends to move relative to the overall market. "
                           "A beta of 1.5 means it tends to move about 50% more than the market, in "
                           "either direction.",
            "why_it_matters": "Higher beta usually means bigger swings — more upside in rallies, more "
                               "downside in selloffs.",
        },
        "Volatility": {
            "definition": "How much and how quickly a price moves around, up or down, over time.",
            "why_it_matters": "Higher volatility means a wider range of possible short-term outcomes — "
                               "not necessarily a worse long-term outcome.",
        },
        "Concentration Risk": {
            "definition": "The risk that comes from having too much of your portfolio in one stock, "
                           "sector, or asset.",
            "why_it_matters": "The opposite of diversification — the more concentrated you are, the more "
                               "a single bad outcome can hurt you.",
        },
        "Drawdown": {
            "definition": "The percentage drop from a portfolio's (or stock's) recent peak to its "
                           "current value.",
            "why_it_matters": "A concrete way to measure 'how bad has it gotten' during a downturn, "
                               "useful for gut-checking your own risk tolerance.",
        },
    },
    "General Terminology": {
        "Market Cap": {
            "definition": "Share price multiplied by total shares outstanding — the total market value "
                           "of a company.",
            "why_it_matters": "Used to categorize companies as large-cap, mid-cap, small-cap, etc., "
                               "which often correlates with stability versus growth potential.",
        },
        "Bull Market / Bear Market": {
            "definition": "A bull market is a sustained period of rising prices; a bear market is a "
                           "sustained period of falling prices (commonly defined as a 20%+ drop).",
            "why_it_matters": "Sets the broad backdrop that most individual stocks move within, to some "
                               "degree.",
        },
        "Fear & Greed Index": {
            "definition": "A gauge of overall market sentiment, from 'extreme fear' to 'extreme greed,' "
                           "often built from volatility, momentum, and other market signals.",
            "why_it_matters": "A rough read on crowd psychology — useful context, not a trading signal "
                               "on its own.",
        },
        "ETF (Exchange-Traded Fund)": {
            "definition": "A fund holding a basket of assets (often many stocks) that trades on an "
                           "exchange just like a single stock.",
            "why_it_matters": "An easy way to get diversification in a single purchase.",
        },
        "Index Fund": {
            "definition": "A fund built to track a specific market index (like the S&P 500) rather than "
                           "trying to beat it.",
            "why_it_matters": "Typically low-cost and historically hard for active strategies to beat "
                               "consistently over the long run.",
        },
    },
}


def get_categories() -> list[str]:
    return list(GLOSSARY.keys())


def get_terms(category: str) -> dict:
    return GLOSSARY.get(category, {})
