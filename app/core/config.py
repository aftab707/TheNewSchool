"""
Configuration settings for Smart CRM (Paramètres de configuration pour Smart CRM)
All tunables and weights live here (Tous les paramètres ajustables et coefficients sont définis ici)
"""
import os
from datetime import date
from dotenv import load_dotenv

# Load environment variables from .env file (Chargement automatique du fichier .env)
load_dotenv()


# ---------------------------------------------------------------------------
# Reference Date Configuration (Configuration de la date de référence)
# ---------------------------------------------------------------------------

def get_today() -> date:
    """
    Return the reference date for the CRM (Retourne la date de référence pour le CRM).
    If CRM_TODAY is defined in .env, use it; otherwise use system date (Si CRM_TODAY est défini, on l'utilise, sinon la date du jour).
    """
    raw = os.environ.get("CRM_TODAY", "").strip()
    if raw:
        return date.fromisoformat(raw)
    return date.today()


# ---------------------------------------------------------------------------
# Scoring Weights (Poids et coefficients pour le calcul de priorité)
# ---------------------------------------------------------------------------

# Weight given to lead value vs contact urgency (Poids accordé à la valeur du lead vs l'urgence de rappel)
WEIGHT_VALUE: float = 0.55
WEIGHT_URGENCY: float = 0.45

# Urgency points calculation (Calcul des points d'urgence)
URGENCY_DUE_TODAY: int = 60          # Base urgency when due today (Urgence de base si contact prévu aujourd'hui)
URGENCY_PER_OVERDUE_DAY: int = 5     # Points added per day overdue (Points ajoutés par jour de retard)
URGENCY_MAX: int = 100               # Urgency ceiling (Plafond d'urgence maximale)
URGENCY_FUTURE_BASE: int = 40        # Base points if due tomorrow (Points de base si prévu demain)
URGENCY_PER_FUTURE_DAY: int = 10     # Points deducted per day in the future (Points déduits par jour futur)

# Value bonuses (Bonus ajoutés à la valeur du prospect)
VALUE_BONUS_INTERESTED: int = 10     # Bonus for confirmed interest (Bonus si intérêt confirmé)
VALUE_BONUS_CALLBACK: int = 10       # Bonus if callback requested (Bonus si rappel demandé)
VALUE_BONUS_FUNDING_PATH: int = 5    # Bonus if eligible funding identified (Bonus si voie de financement identifiée)
VALUE_MAX: int = 100                 # Maximum lead value score (Plafond maximal de valeur)

# Priority bonuses and multipliers (Bonus et multiplicateurs de priorité globale)
BONUS_FORGOTTEN_HOT: int = 15        # Hot lead with only 1 contact attempt (Lead chaud avec un seul appel)
BONUS_CALLBACK_OVERDUE: int = 20     # Promised callback is overdue (Rappel promis en retard)
FATIGUE_MULTIPLIER: float = 0.6      # Multiplier after consecutive unanswered calls (Facteur de fatigue après échecs répétés)
FATIGUE_THRESHOLD: int = 3           # Number of no-answers before fatigue applies (Nombre d'appels sans réponse avant pénalité)
STOP_RULE_CALLS: int = 5             # Stop chasing after N fruitless calls (Arrêt des appels après 5 tentatives sans échange)

# Warmth threshold for hot leads (Seuil de chaleur pour qualifier un lead de 'chaud')
HOT_CHALEUR_THRESHOLD: int = 7


# ---------------------------------------------------------------------------
# Follow-up Cadence (Délai de suivi par palier de chaleur en jours ouvrés)
# ---------------------------------------------------------------------------

CADENCE: dict[str, int] = {
    "hot":    1,   # Chaleur 8-10: follow-up next business day (Lead chaud : rappel à J+1 ouvré)
    "warm":   3,   # Chaleur 5-7: follow-up in 3 business days (Lead tiède : rappel à J+3 ouvrés)
    "cool":   7,   # Chaleur 3-4: follow-up in 7 business days (Lead frais : rappel à J+7 ouvrés)
    "cold":   14,  # Chaleur 0-2: follow-up in 14 business days (Lead froid : rappel à J+14 ouvrés)
}

def cadence_days(chaleur: int) -> int:
    """
    Get standard follow-up days based on warmth (Obtenir le délai standard selon le score de chaleur).
    """
    if chaleur >= 8:
        return CADENCE["hot"]
    if chaleur >= 5:
        return CADENCE["warm"]
    if chaleur >= 3:
        return CADENCE["cool"]
    return CADENCE["cold"]


# ---------------------------------------------------------------------------
# Outcome Specific Follow-ups (Délais spécifiques selon le résultat d'appel)
# ---------------------------------------------------------------------------

OUTCOME_FOLLOWUP_DAYS: dict[str, int | None] = {
    "interested":         2,      # Send quote/info within 2 business days (Envoi de devis sous 2 jours ouvrés)
    "needs_funding_info": 3,      # Follow-up on funding dossier in 3 days (Point dossier financement sous 3 jours)
    "no_answer":          None,   # Falls back to chaleur cadence (Repli sur la cadence standard selon la chaleur)
    "voicemail":          None,   # Same as no-answer (Même règle que pas de réponse)
    "callback_requested": None,   # Date explicitly set by rep (Date fixée manuellement par le commercial)
    "not_interested":     None,   # Closed lost (Lead clôturé en perdu)
    "wrong_number":       None,   # Closed lost (Lead clôturé en faux numéro)
    "enrolled":           None,   # Closed won (Lead clôturé en inscrit)
}
NO_ANSWER_HOT_DAYS: int = 1       # Quick 1-day retry for hot leads after no answer (Relance rapide à 24h pour lead chaud sans réponse)


# ---------------------------------------------------------------------------
# Queue Display Settings (Paramètres d'affichage de la file de travail)
# ---------------------------------------------------------------------------

DAILY_CALL_CAPACITY: int = 15     # Max target calls per rep per day (Capacité journalière conseillée par commercial)
UPCOMING_WINDOW_DAYS: int = 7     # Days ahead to show in upcoming queue (Fenêtre des prochains jours à afficher)

# Recognized official funding sources in France (Organismes de financement reconnus en France)
FUNDING_PATH_STATUSES: set[str] = {"cpf", "opco", "france_travail", "employer"}


# ---------------------------------------------------------------------------
# Database File Path (Chemin du fichier de base de données SQLite)
# ---------------------------------------------------------------------------

DB_PATH: str = os.environ.get("CRM_DB_PATH", "crm.db")
