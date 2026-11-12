import time
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional

FOREX_FACTORY_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

class EconomicNewsFilter:
    """
    📰 Filtro de Noticias Macroeconómicas y Calendario Económico (Forex Factory)
    
    Inspirado en la recomendación de Forex Factory de Ares Viñuela.
    Monitorea eventos económicos de alto impacto ('High Impact / Red Folder') en USD y EUR
    (CPI/IPC, Tipos de Interés FOMC, NFP, PIB) para activar el 'Escudo de Noticias' y evitar
    que el bot abra operaciones durante los latigazos de volatilidad artificial y barridos de stops.
    """

    def __init__(
        self,
        buffer_before_minutes: float = 20.0,
        buffer_after_minutes: float = 15.0,
        cache_ttl_seconds: float = 7200.0, # 2 horas de caché
        timeout: float = 6.0
    ):
        self.buffer_before_minutes = buffer_before_minutes
        self.buffer_after_minutes = buffer_after_minutes
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout = timeout
        
        self.last_fetch_time = 0.0
        self.cached_events: List[Dict] = []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        })

    def fetch_calendar(self, force: bool = False) -> List[Dict]:
        """Obtiene la lista de eventos de la semana desde Forex Factory con caché automático."""
        now = time.time()
        if not force and self.cached_events and (now - self.last_fetch_time < self.cache_ttl_seconds):
            return self.cached_events

        try:
            resp = self.session.get(FOREX_FACTORY_CALENDAR_URL, timeout=self.timeout)
            if resp.status_code == 200:
                raw_events = resp.json()
                if isinstance(raw_events, list):
                    parsed = []
                    for item in raw_events:
                        date_str = item.get("date", "")
                        impact = item.get("impact", "")
                        country = item.get("country", "")
                        title = item.get("title", "")
                        
                        # Solo monitorear eventos de Alto Impacto en USD y EUR
                        if impact == "High" and country in ["USD", "EUR"]:
                            try:
                                dt = datetime.fromisoformat(date_str).astimezone(timezone.utc)
                                parsed.append({
                                    "title": title,
                                    "country": country,
                                    "impact": impact,
                                    "datetime_utc": dt,
                                    "forecast": item.get("forecast", ""),
                                    "previous": item.get("previous", "")
                                })
                            except Exception:
                                continue
                    self.cached_events = parsed
                    self.last_fetch_time = now
                    return self.cached_events
        except Exception:
            pass

        return self.cached_events

    def get_news_status(self, now_override: Optional[datetime] = None) -> Dict:
        """
        Evalúa el estado del calendario en el instante actual.
        Retorna si el Escudo de Noticias está activo, el evento causante y el próximo evento programado.
        """
        now_utc = now_override or datetime.now(timezone.utc)
        events = self.fetch_calendar()

        active_event = None
        next_event = None
        min_future_diff = float("inf")

        for ev in events:
            ev_dt = ev["datetime_utc"]
            diff_min = (ev_dt - now_utc).total_seconds() / 60.0

            # Ventana de Escudo Activo: desde buffer_before_minutes antes hasta buffer_after_minutes después
            if -self.buffer_after_minutes <= diff_min <= self.buffer_before_minutes:
                active_event = {
                    "title": ev["title"],
                    "country": ev["country"],
                    "impact": ev["impact"],
                    "time_utc": ev_dt.strftime("%H:%M UTC"),
                    "minutes_relative": round(diff_min, 1)
                }

            # Identificar el evento futuro más cercano
            if diff_min > self.buffer_before_minutes and diff_min < min_future_diff:
                min_future_diff = diff_min
                hours_until = int(diff_min // 60)
                mins_remainder = int(diff_min % 60)
                time_str = f"{hours_until}h {mins_remainder}m" if hours_until > 0 else f"{mins_remainder}m"
                next_event = {
                    "title": ev["title"],
                    "country": ev["country"],
                    "impact": ev["impact"],
                    "time_utc": ev_dt.strftime("%H:%M UTC (%d/%m)"),
                    "minutes_until": round(diff_min, 0),
                    "countdown": time_str
                }

        is_shield_active = (active_event is not None)

        if is_shield_active:
            summary = f"🛡️ ESCUDO ACTIVO: {active_event['title']} ({active_event['country']}) a las {active_event['time_utc']} - Compras Pausadas"
            badge_text = f"🛡️ ESCUDO ACTIVO ({active_event['country']})"
            badge_color = "#f87171"
        elif next_event:
            summary = f"🟢 Calendario Despejado | Próximo evento clave: {next_event['title']} ({next_event['country']}) en {next_event['countdown']}"
            badge_text = f"📰 {next_event['title']} ({next_event['countdown']})"
            badge_color = "#38bdf8"
        else:
            summary = "🟢 Calendario Despejado | Sin noticias de alto impacto pendientes esta semana"
            badge_text = "🟢 Sin noticias de impacto"
            badge_color = "#4ade80"

        return {
            "is_shield_active": is_shield_active,
            "active_event": active_event,
            "next_event": next_event,
            "high_impact_events_tracked": len(events),
            "summary": summary,
            "badge_text": badge_text,
            "badge_color": badge_color
        }
