# Futures Cheat Code

Personal autonomous futures system. The model thinks for itself, trades a paper prop account, sends phone alerts, and improves from its own results.

## Prop Rules

| Rule | Value |
|------|-------|
| Starting equity | $50,000 |
| Eval profit target | +$3,000 |
| Max loss | $2,000 |
| Eval | Aggressive, RR 1.9 |
| Funded | Protective, lower risk |

## Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Deploy a public app from GitHub
3. Repo: `mikeyacko44-hash/futures-cheatcode`
4. Main file: `app.py`
5. Secrets (optional for alerts):
```toml
TELEGRAM_BOT_TOKEN = "your_token"
TELEGRAM_CHAT_ID = "your_chat_id"
```
