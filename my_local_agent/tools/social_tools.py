# tools/social_tools.py
import os
import tweepy
from langchain_core.tools import tool

def _get_twitter_client():
    """Recupera le chiavi dal file .env e autentica il client Twitter."""
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_secret = os.getenv("TWITTER_ACCESS_SECRET")
    
    if not all([api_key, api_secret, access_token, access_secret]):
        raise ValueError("Credenziali Twitter mancanti nel file .env")
        
    # Autenticazione OAuth 1.0a (necessaria per postare)
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret
    )
    return client

@tool
def pubblica_post_twitter(testo_post: str) -> str:
    """
    Pubblica un post (tweet) sull'account X (Twitter) dell'utente.
    Usa questo strumento QUANDO l'utente ti chiede esplicitamente di scrivere 
    o pubblicare un messaggio sui social.
    """
    print(f"📱 [TOOL: Social] Pubblicazione post su X in corso...")
    
    # Controllo di sicurezza sulla lunghezza
    if len(testo_post) > 280:
        return "❌ Errore: Il testo supera il limite di 280 caratteri di X."
        
    try:
        client = _get_twitter_client()
        response = client.create_tweet(text=testo_post)
        tweet_id = response.data['id']
        return f"✅ Post pubblicato con successo su X! ID del Tweet: {tweet_id}"
        
    except Exception as e:
        return f"❌ Errore durante la pubblicazione sui social: {e}"