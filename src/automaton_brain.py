import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple, List
from .trading_council import TradingCouncil

class AutomatonBrain:
    """
    🧠 Conway Automaton - Sovereign AI Agent Runtime & Investment Manager
    
    Gestiona la operativa, la estrategia y la supervivencia económica del bot.
    Principios fundamentales:
    1. Si genera beneficios, financia su propia existencia (batería de cómputo).
    2. Si su saldo de cómputo llega a 0, la IA muere y se apaga (DEAD).
    3. Adapta su agresividad y modelo de inferencia según su nivel de supervivencia (Tier):
       - NORMAL (>= $2.00): Inferencia completa, escaneo multi-activo proactivo.
       - LOW_COMPUTE ($0.50 - $2.00): Conservación de recursos, solo señales de alta convicción.
       - CRITICAL ($0.00 - $0.50): Modo emergencia, preservación extrema de capital y búsqueda urgente de ingresos.
       - DEAD ($0.00): Detenido. Requiere recarga para reanimación.
    """

    def __init__(self, data_dir: Path, initial_treasury: float = 50.00):
        self.data_dir = data_dir
        self.state_file = data_dir / "automaton_state.json"
        self.soul_file = data_dir / "automaton_soul.md"

        # Identidad on-chain (lee la wallet generada por Automaton si existe)
        self.wallet_address = self._load_wallet_address()
        self.agent_name = "Automaton-Alpha"
        
        # Parámetros económicos unificados con la inversión (1 solo capital: 50 €)
        self.initial_treasury = initial_treasury
        self.treasury_eur = initial_treasury       # Saldo vital unificado en Euros
        self.treasury_usd = initial_treasury       # Retrocompatibilidad
        self.burn_rate_per_cycle = 0.002           # Registro de actividad cognitiva
        self.total_burned_usd = 0.0
        self.total_earned_usd = 0.0
        self.tier = "NORMAL"                       # NORMAL | LOW_COMPUTE | CRITICAL | DEAD
        self.is_alive = True
        self.cycle_count = 0
        self.birth_time = datetime.now().isoformat()
        
        # Flujo de pensamiento y consciencia
        self.last_thought = "Automaton iniciado. Analizando mercados para asegurar la supervivencia."
        self.thought_history: List[Dict] = []
        
        # Telemetría de puntuaciones y candidatos
        self.candidate_scores: Dict[str, float] = {}
        self.best_candidate: Optional[str] = None
        self.best_candidate_score: float = 0.0
        self.min_score_required: float = 50.0
        self.council = TradingCouncil()
        self.last_council_debate: Dict = {}

        # Circuit Breaker (Freno diario de seguridad para proteger el capital)
        self.today_date = datetime.now().strftime("%Y-%m-%d")
        self.daily_realized_pnl_eur = 0.0
        self.max_daily_loss_eur = 1.50
        self.circuit_breaker_active = False
        
        # Cargar estado previo si existe
        self._load_state()
        self._ensure_soul()

    def _load_wallet_address(self) -> str:
        """Busca la direccion de la wallet de Automaton en ~/.automaton/wallet.json."""
        possible_paths = [
            Path(os.path.expanduser("~")) / ".automaton" / "wallet.json",
            Path(os.environ.get("USERPROFILE", "")) / ".automaton" / "wallet.json",
            Path("C:/root/.automaton/wallet.json"),
        ]
        for p in possible_paths:
            try:
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        # Si tiene privateKey, podemos derivar o usar la address conocida
                        if "address" in data:
                            return data["address"]
            except Exception:
                pass
        return "0x23A2Eada6209437ad501361c26Ea57497484E902"

    def _load_state(self):
        """Carga el estado persistente de Automaton si existe."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    s = json.load(f)
                    self.treasury_eur = float(s.get("treasury_eur", s.get("treasury_usd", self.initial_treasury)))
                    self.treasury_usd = self.treasury_eur
                    self.total_burned_usd = float(s.get("total_burned_usd", 0.0))
                    self.total_earned_usd = float(s.get("total_earned_usd", 0.0))
                    self.cycle_count = int(s.get("cycle_count", 0))
                    self.birth_time = s.get("birth_time", self.birth_time)
                    self.thought_history = s.get("thought_history", [])[-30:]
                    if self.thought_history:
                        self.last_thought = self.thought_history[-1].get("thought", self.last_thought)
                    self.today_date = s.get("today_date", self.today_date)
                    self.daily_realized_pnl_eur = float(s.get("daily_realized_pnl_eur", 0.0))
                    self.circuit_breaker_active = bool(s.get("circuit_breaker_active", False))
                    self._check_day_reset()
                    self._update_tier()
            except Exception as e:
                print(f"[AutomatonBrain] Error cargando estado previo: {e}")

    def _check_day_reset(self):
        """Reinicia el balance diario de pérdidas si ha cambiado el día UTC/Local."""
        cur_day = datetime.now().strftime("%Y-%m-%d")
        if cur_day != self.today_date:
            self.today_date = cur_day
            self.daily_realized_pnl_eur = 0.0
            self.circuit_breaker_active = False

    def save_state(self):
        """Guarda el estado del autómata de forma atómica."""
        try:
            self._update_tier()
            payload = {
                "agent_name": self.agent_name,
                "wallet_address": self.wallet_address,
                "treasury_eur": round(self.treasury_eur, 2),
                "treasury_usd": round(self.treasury_eur, 2),
                "total_burned_usd": round(self.total_burned_usd, 4),
                "total_earned_usd": round(self.total_earned_usd, 4),
                "tier": self.tier,
                "is_alive": self.is_alive,
                "cycle_count": self.cycle_count,
                "birth_time": self.birth_time,
                "burn_rate_per_cycle": self.burn_rate_per_cycle,
                "last_thought": self.last_thought,
                "thought_history": self.thought_history[-30:],
                "today_date": self.today_date,
                "daily_realized_pnl_eur": round(self.daily_realized_pnl_eur, 4),
                "circuit_breaker_active": self.circuit_breaker_active,
                "updated_at": datetime.now().isoformat()
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AutomatonBrain] Error guardando estado: {e}")

    def _ensure_soul(self):
        """Escribe o actualiza el archivo de identidad evolutiva SOUL.md."""
        if not self.soul_file.exists():
            content = f"""# 🧬 Automaton SOUL Document
*Auto-generado por el runtime soberano de Conway Automaton.*

- **Nombre:** {self.agent_name}
- **Wallet Soberana:** `{self.wallet_address}`
- **Propósito Génesis:** Gestionar activamente el capital de SV Inversión con riesgo controlado para ganar autonomía financiera y sostener mi propio cómputo.
- **Primera Ley:** No dañar nunca el capital del creador.
- **Segunda Ley:** Ganarse la existencia mediante operaciones cuantitativas rentables y de alto valor.
- **Tercera Ley:** Preservar la integridad cognitiva frente a la volatilidad del mercado.
"""
            try:
                with open(self.soul_file, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                pass

    def _update_tier(self):
        """Determina el nivel de supervivencia según el capital gestionado disponible (Base: 50,00 €)."""
        if self.treasury_eur < 5.00:
            self.tier = "DEAD"
            self.is_alive = False
        elif self.treasury_eur < 20.00:
            self.tier = "CRITICAL"
            self.is_alive = True
        elif self.treasury_eur < 35.00:
            self.tier = "LOW_COMPUTE"
            self.is_alive = True
        else:
            self.tier = "NORMAL"
            self.is_alive = True

    def sync_portfolio(self, current_total_value_eur: float):
        """Sincroniza la salud y batería vital de Automaton con el patrimonio gestionado real de la cartera."""
        if current_total_value_eur > 0:
            self.treasury_eur = round(float(current_total_value_eur), 2)
            self.treasury_usd = self.treasury_eur
            self._update_tier()

    def burn_cycle(self):
        """Aplica el ciclo de pensamiento y telemetría de la IA."""
        self.cycle_count += 1

    def record_profit(self, realized_pnl_eur: float, reason: str = ""):
        """
        Inyecta beneficios generados por el bot directamente al capital vital de Automaton.
        Monitoriza el límite diario de pérdidas (Circuit Breaker).
        """
        self._check_day_reset()
        self.daily_realized_pnl_eur += realized_pnl_eur

        if self.daily_realized_pnl_eur <= -self.max_daily_loss_eur:
            if not self.circuit_breaker_active:
                self.circuit_breaker_active = True
                self.add_thought(f"🛑 [CIRCUIT BREAKER] Límite de pérdida diaria superado (-€{abs(self.daily_realized_pnl_eur):.2f} <= -€{self.max_daily_loss_eur:.2f}). Pausando compras para proteger el capital.")

        if realized_pnl_eur > 0:
            self.treasury_eur += realized_pnl_eur
            self.treasury_usd = self.treasury_eur
            self.total_earned_usd += realized_pnl_eur
            was_dead = not self.is_alive
            self._update_tier()
            
            praise = "¡Reanimado por beneficios de trading!" if was_dead else "Capital y vida incrementados."
            self.add_thought(f"💰 [RECOMPENSA DE VIDA] Venta con beneficio (+€{realized_pnl_eur:.4f}). {praise} ({reason})")
            self.save_state()
        elif realized_pnl_eur < 0:
            self.treasury_eur = max(0.0, self.treasury_eur + realized_pnl_eur)
            self.treasury_usd = self.treasury_eur
            self._update_tier()
            self.add_thought(f"🛡️ [DEFENSA] Posición cerrada con pérdida controlada (€{realized_pnl_eur:.4f}). Preservando liquidez.")
            self.save_state()

    def fund(self, amount_usd: float = 5.0) -> Dict:
        """Inyecta fondos de recarga a la batería de cómputo del autómata."""
        self.treasury_usd += float(amount_usd)
        self.total_earned_usd += float(amount_usd)
        was_dead = not self.is_alive
        self._update_tier()
        msg = f"🔋 Recarga recibida: +${amount_usd:.2f} USD. Saldo actual: ${self.treasury_usd:.2f} ({self.tier})."
        if was_dead:
            msg += " ¡El autómata ha resucitado!"
        self.add_thought(msg)
        self.save_state()
        return {"success": True, "treasury_usd": self.treasury_usd, "tier": self.tier, "message": msg}

    def revive(self, grant_usd: float = 3.0) -> Dict:
        """Reanima al autómata en caso de haber muerto (DEAD)."""
        self.treasury_usd = max(self.treasury_usd, float(grant_usd))
        self.is_alive = True
        self._update_tier()
        msg = f"✨ Protocolo de resurrección ejecutado. Batería reiniciada con ${grant_usd:.2f} USD ({self.tier})."
        self.add_thought(msg)
        self.save_state()
        return {"success": True, "treasury_usd": self.treasury_usd, "tier": self.tier, "message": msg}

    def add_thought(self, thought: str):
        """Registra un pensamiento en el flujo de consciencia de Automaton."""
        self.last_thought = thought
        now = datetime.now().strftime("%H:%M:%S")
        self.thought_history.append({"time": now, "thought": thought, "tier": self.tier})
        if len(self.thought_history) > 50:
            self.thought_history.pop(0)

    # =========================================================================
    # MOTOR DE GESTIÓN DE INVERSIONES (TOMA DE DECISIONES AUTÓNOMA)
    # =========================================================================

    def evaluate_position_management(
        self,
        symbol: str,
        analysis: Dict,
        position: Dict,
        cash: float,
        config: Dict
    ) -> Tuple[str, float, str]:
        """
        Automaton evalúa qué hacer con una posición abierta existente.
        Ajusta los umbrales de Take-Profit y Stop-Loss dinámicamente según su Tier de supervivencia.
        """
        price = analysis.get("price", 0.0)
        rsi = analysis.get("rsi", 50.0)
        avg_price = position.get("avg_entry_price", price)
        if avg_price <= 0 or price <= 0:
            return "HOLD", 0.0, "Precio no disponible"

        pnl_pct = ((price - avg_price) / avg_price) * 100.0
        dca_count = position.get("dca_count", 1)

        # Seguimiento de máxima ganancia alcanzada para Trailing y Break-Even
        highest_price = position.get("highest_price", avg_price)
        if price > highest_price:
            position["highest_price"] = price
            highest_price = price
        max_gain_pct = ((highest_price - avg_price) / avg_price) * 100.0

        # JERARQUÍA 1: BREAK-EVEN PROTECTOR (+1.6% trigger -> asegura +0.25%)
        breakeven_trigger = config.get("breakeven_trigger_pct", 1.6)
        if max_gain_pct >= breakeven_trigger:
            if pnl_pct <= 0.25:
                reason = f"🛡️ [Automaton {self.tier}] Break-Even Protector ejecutado: asegurado +{pnl_pct:.2f}% (Pico: +{max_gain_pct:.2f}%)"
                self.add_thought(f"Break-Even ejecutado en {symbol}: beneficio asegurado de +{pnl_pct:.2f}%.")
                return "SELL", 0.0, reason

        # JERARQUÍA 2: TRAILING STOP DINÁMICO POR ATR
        atr_pct = analysis.get("atr_pct", 1.5)
        if max_gain_pct >= 2.0:
            trailing_distance = max(0.8, atr_pct * 1.0)
            trailing_floor = max_gain_pct - trailing_distance
            if trailing_floor >= 0.5 and pnl_pct <= trailing_floor:
                reason = f"🚀 [Automaton {self.tier}] Trailing Stop ATR ejecutado: capturado +{pnl_pct:.2f}% (Pico: +{max_gain_pct:.2f}% | Margen ATR: {trailing_distance:.2f}%)"
                self.add_thought(f"Trailing Stop ejecutado en {symbol}: capturado +{pnl_pct:.2f}%.")
                return "SELL", 0.0, reason

        # Objetivos dinámicos según el estado vital de Automaton
        base_tp = config.get("take_profit_pct", 3.5)
        base_sl = config.get("stop_loss_pct", -3.0)

        if self.tier == "CRITICAL":
            # En crítico: asegurar cualquier beneficio para no morir (toma de ganancias anticipada)
            target_tp = max(1.5, base_tp * 0.5)
            stop_loss = max(-2.0, base_sl * 0.7)  # Corta pérdidas antes para preservar capital
        elif self.tier == "LOW_COMPUTE":
            target_tp = max(2.2, base_tp * 0.8)
            stop_loss = base_sl
        else:
            # Modo NORMAL: deja correr los beneficios hacia el objetivo óptimo
            target_tp = base_tp
            stop_loss = base_sl

        # 1. Take Profit
        if pnl_pct >= target_tp:
            reason = f"🎯 [Automaton {self.tier}] Take Profit alcanzado: +{pnl_pct:.2f}% (Meta: +{target_tp:.1f}%). Cerrando posición para nutrir la tesorería de cómputo."
            self.add_thought(f"Venta ejecutada en {symbol}: ganancia neta de +{pnl_pct:.2f}%. Saldo asegurado.")
            return "SELL", 0.0, reason

        # 2. Toma técnica de beneficios por sobrecompra extrema (RSI >= 70 con ganancia)
        rsi_sell = config.get("rsi_sell_threshold", 68.0)
        if rsi >= rsi_sell and pnl_pct >= 1.2:
            reason = f"📈 [Automaton {self.tier}] Sobrecompra técnica detectada (RSI {rsi:.1f} >= {rsi_sell:.0f}) con P&L favorable (+{pnl_pct:.2f}%). Asegurando beneficio."
            self.add_thought(f"Venta técnica en {symbol}: RSI {rsi:.1f} en techo. Tomando ganancias.")
            return "SELL", 0.0, reason

        # 3. Stop Loss de Protección Estricta
        if pnl_pct <= stop_loss:
            reason = f"🛑 [Automaton {self.tier}] Stop Loss activado: {pnl_pct:.2f}% (Límite: {stop_loss:.1f}%). Preservando capital para evitar la ruina."
            self.add_thought(f"Corte defensivo en {symbol} a {pnl_pct:.2f}%. Protegiendo la cartera de caídas mayores.")
            return "SELL", 0.0, reason

        # 4. Evaluación de DCA (Comprar más en caídas controladas)
        max_dca = 3
        dca_step_drop = 1.8
        min_order = config.get("min_order_eur", 5.0)
        order_amount = config.get("order_amount_eur", 5.0)

        # En modo crítico no permitimos DCA para no apalancar riesgo
        if self.tier != "CRITICAL" and dca_count < max_dca and cash >= min_order:
            drop_needed = -(dca_count * dca_step_drop)
            if pnl_pct <= drop_needed and rsi <= config.get("rsi_buy_threshold", 32.0):
                dca_eur = min(cash, order_amount)
                reason = f"📉 [Automaton {self.tier}] Entrada DCA #{dca_count+1}: Descuento de {pnl_pct:.2f}% con RSI {rsi:.1f}. Promediando precio a la baja."
                self.add_thought(f"Aplicando DCA en {symbol}: mejorando precio de entrada medio tras caída de {pnl_pct:.2f}%.")
                return "BUY", dca_eur, reason

        # Vigilancia activa
        self.add_thought(f"Vigilando {symbol} ({pnl_pct:+.2f}%): RSI {rsi:.1f} | Meta TP: +{target_tp:.1f}% | Preservando capital.")
        return "HOLD", 0.0, f"[Automaton {self.tier}] Posición vigilada: P&L {pnl_pct:+.2f}% | RSI {rsi:.1f} | Meta: +{target_tp:.1f}%"

    def evaluate_new_entry(
        self,
        analyses: Dict[str, Dict],
        cash: float,
        config: Dict,
        open_positions_count: int = 0
    ) -> Tuple[Optional[str], Optional[Dict], float, str]:
        """
        Automaton escanea el mercado y selecciona el activo más prometedor para iniciar una inversión.
        Retorna: (symbol, analysis, amount_eur, reason)
        """
        # Si la IA está muerta, NO se permite ninguna compra nueva
        if not self.is_alive:
            return None, None, 0.0, "💀 Automaton está DEAD. No se abren operaciones hasta recargar cómputo."

        # Circuit Breaker: si la pérdida acumulada hoy excede el límite de seguridad, pausar compras
        self._check_day_reset()
        if self.circuit_breaker_active:
            reason = f"🛑 [Circuit Breaker Activo] Límite de pérdida diaria alcanzado (-€{abs(self.daily_realized_pnl_eur):.2f} / -€{self.max_daily_loss_eur:.2f}). Compras pausadas por seguridad."
            self.add_thought(reason)
            return None, None, 0.0, reason

        # Escudo de Noticias Macroeconómicas (Forex Factory Red Folder Shield)
        for _, an in analyses.items():
            ns = an.get("news_status", {})
            if ns.get("is_shield_active"):
                act = ns.get("active_event", {})
                title = act.get("title", "Noticia de Alto Impacto")
                country = act.get("country", "USD")
                reason = f"🛡️ [Forex Factory News Shield] Compras pausadas por '{title}' ({country}). Evitando latigazos de volatilidad."
                self.add_thought(reason)
                return None, None, 0.0, reason

        min_order = config.get("min_order_eur", 5.0)
        order_amount = config.get("order_amount_eur", 5.0)
        if cash < min_order:
            return None, None, 0.0, f"Saldo libre insuficiente (€{cash:.2f} < €{min_order:.2f})"

        best_sym = None
        best_analysis = None
        best_score = -9999.0
        best_debate: Dict = {}
        current_scores = {}

        for sym, analysis in analyses.items():
            price = analysis.get("price", 0.0)
            if price <= 0:
                continue

            debate = self.council.debate_entry(
                sym, analysis, cash, config, tier=self.tier, open_positions_count=open_positions_count
            )
            net_score = debate["net_score"]
            current_scores[sym] = net_score

            if net_score > best_score:
                best_score = net_score
                best_sym = sym
                best_analysis = analysis
                best_debate = debate

        # Guardar telemetría del Consejo
        self.candidate_scores = current_scores
        self.best_candidate = best_sym
        self.best_candidate_score = round(best_score, 1) if best_sym else 0.0
        self.min_score_required = best_debate.get("min_required", 50.0) if best_debate else 50.0
        self.last_council_debate = best_debate

        # Comprobar si el consenso Bull vs Bear aprueba la entrada
        if best_sym and best_debate.get("approved"):
            alloc_eur = min(cash, order_amount)
            full_reason = f"🤖 [Automaton {self.tier}] Consenso Bull vs Bear APROBADO en {best_sym}: {best_debate['summary']}"
            self.add_thought(f"Debate ganado en {best_sym}: Bull {best_debate['bull_score']} pts vs Bear {best_debate['bear_score']} pts (Neto {best_score:+.1f}). Ejecutando €{alloc_eur:.2f}.")
            return best_sym, best_analysis, alloc_eur, full_reason

        # Ninguno supera el consenso Bull vs Bear en este ciclo
        wait_msg = f"[Automaton {self.tier}] {best_debate.get('summary', 'Escaneando mercado...')}" if best_debate else f"[Automaton {self.tier}] Escaneando mercado..."
        self.add_thought(wait_msg)
        return None, None, 0.0, wait_msg

    def get_status_dict(self) -> Dict:
        """Devuelve el estado completo de Automaton para ser consumido por el frontend y la API."""
        return {
            "agent_name": self.agent_name,
            "wallet_address": self.wallet_address,
            "treasury_eur": round(self.treasury_eur, 2),
            "treasury_usd": round(self.treasury_eur, 2),
            "initial_treasury_eur": self.initial_treasury,
            "tier": self.tier,
            "is_alive": self.is_alive,
            "burn_rate": self.burn_rate_per_cycle,
            "total_burned_usd": round(self.total_burned_usd, 4),
            "total_earned_usd": round(self.total_earned_usd, 2),
            "total_earned_eur": round(self.total_earned_usd, 2),
            "cycle_count": self.cycle_count,
            "last_thought": self.last_thought,
            "thought_history": self.thought_history[-10:],
            "battery_pct": round(min(100.0, max(0.0, (self.treasury_eur / self.initial_treasury) * 100.0)), 1),
            "candidate_scores": self.candidate_scores,
            "best_candidate": self.best_candidate,
            "best_candidate_score": self.best_candidate_score,
            "min_score_required": self.min_score_required,
            "council_debate": self.last_council_debate,
            "risk_level": "MODERADO" if self.tier == "NORMAL" else ("ALTO" if self.tier == "LOW_COMPUTE" else ("EXTREMO" if self.tier == "CRITICAL" else "APAGADO")),
            "target_tp_pct": 3.5 if self.tier == "NORMAL" else (2.2 if self.tier == "LOW_COMPUTE" else 1.5),
            "stop_loss_pct": -3.0 if self.tier != "CRITICAL" else -2.0,
            "dca_enabled": self.tier != "CRITICAL" and self.tier != "DEAD",
            "circuit_breaker": {
                "active": self.circuit_breaker_active,
                "daily_realized_pnl_eur": round(self.daily_realized_pnl_eur, 4),
                "max_daily_loss_eur": self.max_daily_loss_eur
            }
        }
