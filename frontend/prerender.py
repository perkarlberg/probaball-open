#!/usr/bin/env python3
"""
Prerender static, crawlable HTML for every route, in every supported language,
from the canonical simulation:
  /                  English home (root, x-default)  /sv/  /es/  /fr/  /pt/  /de/
  /lag/<slug>/       one page per team               + /<lang>/lag/<slug>/
  /grupp/<x>/        one page per group              + /<lang>/grupp/<x>/
plus a sitemap index (sitemap.xml -> sitemap-<lang>.xml children) with hreflang
alternates (incl. region-targeted en-IN) and lastmod.

Each page gets its own <html lang>, title, meta description, canonical (self),
Open Graph locale, reciprocal hreflang alternates, and a BreadcrumbList. React
replaces #root for real users; search engines and JS-less AI crawlers get real,
localized content.

Usage: prerender.py <api_base> <dist_index_html>
"""
import datetime
import html
import json
import os
import re
import sys
import unicodedata
import urllib.request

ORIGIN = "https://probaball.online"

# English is the default (served at the root); the rest get a path prefix
# (incl. Swedish at /sv/). Order: root language first.
LANGS = ["en", "sv", "es", "fr", "pt", "de"]
ROOT_LANG = "en"
# Region-targeted hreflang alternates that reuse an existing language's pages
# (no separate translation). India searches the World Cup in English on Google,
# so en-IN points at the English (root) pages to add an India geo signal.
REGION_ALTERNATES = {"en-IN": "en"}
OG_LOCALE = {"sv": "sv_SE", "en": "en_US", "es": "es_ES",
             "fr": "fr_FR", "pt": "pt_BR", "de": "de_DE"}
# Thousands separator and percent formatting per language.
THOUSANDS = {"sv": " ", "en": ",", "es": ".", "fr": " ", "pt": ".", "de": "."}
DECIMAL_COMMA = {"sv", "es", "fr", "pt", "de"}  # en uses a decimal point


def fmt_n(n, lang):
    return f"{n:,}".replace(",", THOUSANDS[lang])


def pct(v, lang):
    s = f"{v * 100:.1f}"
    if lang in DECIMAL_COMMA:
        return s.replace(".", ",") + " %"
    return s + "%"


def esc(s):
    return html.escape(str(s))


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


# ----------------------------------------------------------------------
# Translations for the prerendered prose. Keys carry {placeholders}.
# ----------------------------------------------------------------------
T = {
    "sv": {
        "wc": "fotbolls-VM 2026",
        "group_word": "Grupp",
        "home_h1": "Fotbolls-VM 2026: prognoser – vem vinner?",
        "home_intro": "Probaball har simulerat hela fotbolls-VM 2026 {n} gånger, baserat på en blandning av lagrankingar (Elo), ledande oddsmakare och {nexp} experter. Nedan är varje lags sannolikhet att bli världsmästare (underlag {date}).",
        "home_h2_champ": "Världsmästare 2026 – sannolikheter",
        "home_li": "{team} (grupp {g}) – {pct} att vinna VM.",
        "home_h2_teams": "Lag",
        "home_h2_groups": "Grupper",
        "home_h2_how": "Så räknar Probaball",
        "home_how1": "Probaball väger samman många oberoende signaler till en prognos – ungefär som ett snitt av många opinionsmätningar (en poll of polls). Varje lags styrka är en viktad blandning (47,5 % rankingar, 47,5 % bookmakers, 5 % experter): en Elo-rating beräknad från ~50 000 landskamper (World Football Elo, eloratings.net), avvigade vinnarodds från {books} (marknadsodds hör till de mest träffsäkra utfallsprognoserna; Forrest, Goddard & Simmons, 2005) och prediktioner från {nexp} experter. Matcherna avgörs med en Dixon-Coles-målmodell i det officiella slutspelsträdet, och hela turneringen spelas upp {n} gånger.",
        "home_how2": "Varje modellförbättring testas mot historiska resultat (out-of-sample, Ranked Probability Score; Constantinou & Fenton, 2012); det som inte träffar bättre slängs (t.ex. tillförde varken FIFA-rankingen eller en attack/försvars-modell något). Det är sannolikheter, inte facit. Probaball är inte anslutet till eller godkänt av FIFA.",
        "team_h1": "{name} – chans att vinna fotbolls-VM 2026",
        "team_p1": "Enligt Probaballs data science-simulering ({n} simuleringar, underlag {date}) har {name} {champ} chans att vinna VM 2026, {final} att nå final, {semi} till semifinal och {r16} till åttondelsfinal. {name} spelar i grupp {g}.",
        "team_p2": "Lagets styrka väger samman lagrankingar (Elo), bookmakerodds och expertprediktioner (47.5/47.5/5). I FIFA-rankingen ligger {name} #{r} av de 48 lagen i turneringen.",
        "group_link": "Grupp {g}",
        "group_h1": "Grupp {g} – fotbolls-VM 2026",
        "group_intro": "Simulerade sannolikheter för grupp {g} i fotbolls-VM 2026 (data science-simulering, underlag {date}):",
        "group_li": "{team}: vinner gruppen {first}, topp 2 {top2}.",
        "home_title": "Fotbolls-VM 2026: prognoser & odds – vem vinner? | Probaball",
        "home_desc": "Uppdateras dagligen efter varje match. Prognoser för fotbolls-VM 2026 – vem vinner, varje lags titelchans och en prognos för varje match, från 50 000 simuleringar.",
        "home_updated": "Uppdateras dagligen · prognos {date} · {played} av {total} matcher spelade",
        "home_h2_matches": "VM-matcher: prognoser",
        "home_matches_intro": "Modellens vinstchans för varje match, uppdaterad efter varje resultat.",
        "home_upcoming": "Kommande matcher",
        "home_results": "Senaste resultaten mot vår prognos",
        "home_vs": "–",
        "home_draw": "Oavgjort",
        "home_called": "som förutspått",
        "home_upset": "skräll",
        "home_all_results": "Alla resultat & träffsäkerhet",
        "home_bracket_link": "Alla slutspelsprognoser",
        "bracket_crumb": "Slutspel",
        "bracket_h1": "Slutspelsprognoser för fotbolls-VM 2026",
        "bracket_title": "VM 2026 slutspel: prognoser & sannolikheter | Probaball",
        "bracket_desc": "Uppdateras dagligen. Slutspelsprognoser för fotbolls-VM 2026 – varje lags chans till åttondel, kvartsfinal, semifinal, final och VM-titel, från 50 000 simuleringar.",
        "bracket_intro": "Varje lags chans att nå varje slutspelsrunda i fotbolls-VM 2026, från {n} simuleringar (underlag {date}). Slutspelsmötena låses när gruppspelet är klart – då går prognoser match för match live.",
        "br_win": "Vinst", "br_final": "Final", "br_sf": "Semi", "br_qf": "Kvart", "br_r16": "Åttondel",
        "team_title": "{name} – chans att vinna VM 2026 | Probaball",
        "team_desc": "{name}: {champ} chans att vinna fotbolls-VM 2026, {final} till final. Sannolikheter från lagrankingar, oddsmakare och experter.",
        "group_title": "Grupp {g} – fotbolls-VM 2026 | Probaball",
        "group_desc": "Grupp {g} i VM 2026: simulerade sannolikheter för varje lag att gå vidare från gruppspelet.",
        "match_title": "{home} – {away}: prognos & vinstchans | VM 2026",
        "match_desc": "{home} – {away} vinstchans i fotbolls-VM 2026: {home} {ph}, oavgjort {pd}, {away} {pa}. Sannolikaste resultat {score}, från Probaballs modell med 50 000 simuleringar.",
        "match_h1": "{home} – {away}: prognos & vinstchans i fotbolls-VM 2026",
        "match_intro": "Vinstchans för {home} – {away} (även {away} – {home}) i fotbolls-VM 2026: {home} {ph}, oavgjort {pd}, {away} {pa}. Sannolikaste resultat är {score}. Från Probaballs modell – 50 000 Monte Carlo-simuleringar som väger Elo, bookmakerodds och experter, validerad out-of-sample.",
        "faq_h2": "Vanliga frågor",
        "faq_q_who": "Vem vinner {home} – {away}?",
        "faq_a_who": "Probaballs modell ger {home} {ph} vinstchans, {away} {pa} och {pd} chans för oavgjort.",
        "faq_q_score": "Vad är det sannolikaste resultatet?",
        "faq_a_score": "Det sannolikaste resultatet är {score}.",
        "faq_q_how": "Hur beräknas vinstchansen?",
        "faq_a_how": "Från 50 000 Monte Carlo-simuleringar som väger samman lagens Elo-rating, bookmakerodds och expertprediktioner – en modell validerad out-of-sample mot tidigare resultat.",
        "crumb_home": "Hem",
        "eval_crumb": "Utvärdering",
        "eval_h1": "Hur träffsäker är VM-prognosen 2026?",
        "eval_title": "Hur träffsäker är VM-prognosen 2026? | Probaball",
        "eval_desc": "Hur bra träffar Probaballs VM-prognos 2026? Prognoser före match mäts med Ranked Probability Score (RPS), med kalibreringsdiagram och resultat match för match.",
        "eval_intro": "Probaball mäter sina prognoser före match mot de faktiska resultaten med Ranked Probability Score (RPS) – det vedertagna vetenskapliga måttet för fotbollsprognoser (Constantinou & Fenton, 2012). Efter {n} gruppspelsmatcher är snitt-RPS {rps} (lägre är bättre; publicerade ligamodeller ligger runt 0,19–0,22). Modellens mest sannolika utfall har inträffat i {called} av {n} matcher, med {upsets} skrällar hittills.",
        "eval_intro_empty": "Här mäter Probaball sina prognoser före match mot de faktiska resultaten med Ranked Probability Score (RPS) – det vedertagna vetenskapliga måttet för fotbollsprognoser (Constantinou & Fenton, 2012). Kom tillbaka när VM 2026 har börjat.",
    },
    "en": {
        "wc": "2026 World Cup",
        "group_word": "Group",
        "home_h1": "2026 World Cup Predictions: Who Will Win?",
        "home_intro": "Probaball has simulated the entire 2026 World Cup {n} times, based on a blend of team rankings (Elo), leading bookmakers and {nexp} experts. Below is each team's probability of becoming world champion (data as of {date}).",
        "home_h2_champ": "World champion 2026 – probabilities",
        "home_li": "{team} (group {g}) – {pct} to win the World Cup.",
        "home_h2_teams": "Teams",
        "home_h2_groups": "Groups",
        "home_h2_how": "How Probaball calculates",
        "home_how1": "Probaball combines several independent signals into one forecast – much like averaging many polls (a poll of polls). Each team's strength is a weighted blend (47.5% rankings, 47.5% bookmakers, 5% experts): an Elo rating computed from ~50,000 internationals (World Football Elo, eloratings.net), de-vigged title odds from {books} (market odds are among the most accurate outcome forecasts; Forrest, Goddard & Simmons, 2005) and predictions from {nexp} experts. Matches are decided with a Dixon-Coles goal model in the official knockout bracket, and the whole tournament is played out {n} times.",
        "home_how2": "Every model improvement is tested against historical results (out-of-sample, Ranked Probability Score; Constantinou & Fenton, 2012); anything that doesn't predict better is dropped (e.g. neither the FIFA ranking nor an attack/defence model added anything). These are probabilities, not certainties. Probaball is not affiliated with or endorsed by FIFA.",
        "team_h1": "{name} – chance to win the 2026 World Cup",
        "team_p1": "According to Probaball's data-science simulation ({n} simulations, data as of {date}), {name} has a {champ} chance to win the 2026 World Cup, {final} to reach the final, {semi} to the semi-finals and {r16} to the round of 16. {name} plays in group {g}.",
        "team_p2": "The team's strength weights team rankings (Elo), bookmaker odds and expert predictions (47.5/47.5/5). In the FIFA ranking {name} sits #{r} of the 48 teams in the tournament.",
        "group_link": "Group {g}",
        "group_h1": "Group {g} – 2026 World Cup",
        "group_intro": "Simulated probabilities for group {g} at the 2026 World Cup (data-science simulation, data as of {date}):",
        "group_li": "{team}: wins the group {first}, top 2 {top2}.",
        "home_title": "2026 World Cup Predictions: Who Will Win? Odds | Probaball",
        "home_desc": "Updated daily after every match. World Cup 2026 predictions — who will win, each team's title odds and a forecast for every game, from 50,000 simulations.",
        "home_updated": "Updated daily · forecast {date} · {played} of {total} matches played",
        "home_h2_matches": "World Cup match predictions",
        "home_matches_intro": "A model win probability for every game, updated after each result.",
        "home_upcoming": "Upcoming matches",
        "home_results": "Recent results vs our prediction",
        "home_vs": "vs",
        "home_draw": "Draw",
        "home_called": "as predicted",
        "home_upset": "upset",
        "home_all_results": "Full results & forecast accuracy",
        "home_bracket_link": "Full bracket predictions",
        "bracket_crumb": "Bracket",
        "bracket_h1": "2026 World Cup Bracket Predictions",
        "bracket_title": "2026 World Cup Bracket Predictions: Knockout Odds | Probaball",
        "bracket_desc": "Updated daily. World Cup 2026 bracket predictions — each team's odds to reach the Round of 16, quarter-final, semi-final, final and win the title, from 50,000 simulations.",
        "bracket_intro": "Each team's chance to reach every knockout round of the 2026 World Cup, from {n} simulations (data as of {date}). Knockout pairings lock when the group stage ends — match-by-match predictions go live then.",
        "br_win": "Win", "br_final": "Final", "br_sf": "Semi", "br_qf": "QF", "br_r16": "R16",
        "team_title": "{name} – chance to win the 2026 World Cup | Probaball",
        "team_desc": "{name}: {champ} chance to win the 2026 World Cup, {final} to the final. Probabilities from team rankings, bookmakers and experts.",
        "group_title": "Group {g} – 2026 World Cup | Probaball",
        "group_desc": "Group {g} at the 2026 World Cup: simulated probabilities for each team to advance from the group stage.",
        "match_title": "{home} vs {away}: prediction & win probability | World Cup 2026",
        "match_desc": "{home} vs {away} win probability at the 2026 World Cup: {home} {ph}, draw {pd}, {away} {pa}. Most likely score {score}, from Probaball's 50,000-run model.",
        "match_h1": "{home} vs {away}: 2026 World Cup prediction & win probability",
        "match_intro": "Win probability for {home} vs {away} (also searched {away} vs {home}) at the 2026 World Cup: {home} {ph}, draw {pd}, {away} {pa}. The most likely score is {score}. From Probaball's model — a 50,000-run Monte Carlo blending Elo, bookmaker odds and experts, validated out-of-sample.",
        "faq_h2": "Frequently asked questions",
        "faq_q_who": "Who will win {home} vs {away}?",
        "faq_a_who": "Probaball's model gives {home} a {ph} win probability, {away} {pa}, and a {pd} chance of a draw.",
        "faq_q_score": "What is the most likely score?",
        "faq_a_score": "The most likely score is {score}.",
        "faq_q_how": "How is the win probability calculated?",
        "faq_a_how": "From a 50,000-run Monte Carlo blending team Elo ratings, bookmaker odds and expert predictions — a model validated out-of-sample against past results.",
        "crumb_home": "Home",
        "eval_crumb": "Evaluation",
        "eval_h1": "How accurate is the 2026 World Cup forecast?",
        "eval_title": "How accurate is the 2026 World Cup forecast? | Probaball",
        "eval_desc": "How well is Probaball's 2026 World Cup forecast doing? Pre-match predictions scored with the Ranked Probability Score (RPS), plus a calibration chart and game-by-game results.",
        "eval_intro": "Probaball scores its pre-match predictions against the actual results using the Ranked Probability Score (RPS) — the standard scientific metric for football forecasts (Constantinou & Fenton, 2012). After {n} group games the average RPS is {rps} (lower is better; published league models score about 0.19–0.22). The model's most likely outcome has come in {called} of {n} games, with {upsets} upsets so far.",
        "eval_intro_empty": "Probaball will score its pre-match predictions against the actual results here, using the Ranked Probability Score (RPS) — the standard scientific metric for football forecasts (Constantinou & Fenton, 2012). Check back once the 2026 World Cup is under way.",
    },
    "es": {
        "wc": "Mundial 2026",
        "group_word": "Grupo",
        "home_h1": "Pronósticos del Mundial 2026: ¿quién ganará?",
        "home_intro": "Probaball ha simulado todo el Mundial 2026 {n} veces, a partir de una mezcla de rankings de equipos (Elo), las principales casas de apuestas y {nexp} expertos. Abajo está la probabilidad de cada equipo de ser campeón del mundo (datos a {date}).",
        "home_h2_champ": "Campeón del mundo 2026 – probabilidades",
        "home_li": "{team} (grupo {g}) – {pct} de ganar el Mundial.",
        "home_h2_teams": "Equipos",
        "home_h2_groups": "Grupos",
        "home_h2_how": "Cómo calcula Probaball",
        "home_how1": "Probaball combina varias señales independientes en un único pronóstico, parecido a promediar muchas encuestas (un poll of polls). La fuerza de cada equipo es una mezcla ponderada (47,5 % rankings, 47,5 % casas de apuestas, 5 % expertos): un rating Elo calculado sobre ~50 000 partidos internacionales (World Football Elo, eloratings.net), cuotas de título sin margen de {books} (las cuotas del mercado están entre las predicciones de resultados más precisas; Forrest, Goddard & Simmons, 2005) y predicciones de {nexp} expertos. Los partidos se deciden con un modelo de goles Dixon-Coles en el cuadro final oficial, y todo el torneo se juega {n} veces.",
        "home_how2": "Cada mejora del modelo se prueba contra resultados históricos (out-of-sample, Ranked Probability Score; Constantinou & Fenton, 2012); lo que no acierta mejor se descarta (p. ej., ni el ranking FIFA ni un modelo de ataque/defensa aportaron nada). Son probabilidades, no certezas. Probaball no está afiliado ni avalado por la FIFA.",
        "team_h1": "{name} – probabilidad de ganar el Mundial 2026",
        "team_p1": "Según la simulación de data science de Probaball ({n} simulaciones, datos a {date}), {name} tiene un {champ} de ganar el Mundial 2026, {final} de llegar a la final, {semi} a semifinales y {r16} a octavos. {name} juega en el grupo {g}.",
        "team_p2": "La fuerza del equipo pondera rankings (Elo), cuotas de apuestas y predicciones de expertos (47.5/47.5/5). En el ranking FIFA, {name} ocupa el puesto #{r} de los 48 equipos del torneo.",
        "group_link": "Grupo {g}",
        "group_h1": "Grupo {g} – Mundial 2026",
        "group_intro": "Probabilidades simuladas para el grupo {g} del Mundial 2026 (simulación de data science, datos a {date}):",
        "group_li": "{team}: gana el grupo {first}, top 2 {top2}.",
        "home_title": "Pronósticos Mundial 2026: ¿quién ganará? Cuotas | Probaball",
        "home_desc": "Actualizado a diario tras cada partido. Pronósticos del Mundial 2026: quién ganará, la probabilidad de título de cada equipo y un pronóstico para cada partido, de 50 000 simulaciones.",
        "home_updated": "Actualizado a diario · pronóstico {date} · {played} de {total} partidos jugados",
        "home_h2_matches": "Pronósticos de partidos del Mundial",
        "home_matches_intro": "La probabilidad de victoria del modelo para cada partido, actualizada tras cada resultado.",
        "home_upcoming": "Próximos partidos",
        "home_results": "Resultados recientes vs nuestro pronóstico",
        "home_vs": "vs",
        "home_draw": "Empate",
        "home_called": "como se predijo",
        "home_upset": "sorpresa",
        "home_all_results": "Todos los resultados y acierto",
        "home_bracket_link": "Pronósticos del cuadro completo",
        "bracket_crumb": "Eliminatorias",
        "bracket_h1": "Pronósticos del cuadro del Mundial 2026",
        "bracket_title": "Cuadro del Mundial 2026: pronósticos y probabilidades | Probaball",
        "bracket_desc": "Actualizado a diario. Pronósticos del cuadro del Mundial 2026: la probabilidad de cada equipo de llegar a octavos, cuartos, semifinal, final y ganar el título, de 50 000 simulaciones.",
        "bracket_intro": "La probabilidad de cada equipo de alcanzar cada ronda eliminatoria del Mundial 2026, de {n} simulaciones (datos a {date}). Los cruces se fijan al terminar la fase de grupos: entonces se publican los pronósticos partido a partido.",
        "br_win": "Título", "br_final": "Final", "br_sf": "Semis", "br_qf": "Cuartos", "br_r16": "Octavos",
        "team_title": "{name} – probabilidad de ganar el Mundial 2026 | Probaball",
        "team_desc": "{name}: {champ} de ganar el Mundial 2026, {final} a la final. Probabilidades de rankings, casas de apuestas y expertos.",
        "group_title": "Grupo {g} – Mundial 2026 | Probaball",
        "group_desc": "Grupo {g} del Mundial 2026: probabilidades simuladas de que cada equipo avance de la fase de grupos.",
        "match_title": "{home} vs {away}: pronóstico y probabilidad | Mundial 2026",
        "match_desc": "Probabilidad de victoria de {home} vs {away} en el Mundial 2026: {home} {ph}, empate {pd}, {away} {pa}. Resultado más probable {score}, del modelo de Probaball con 50 000 simulaciones.",
        "match_h1": "{home} vs {away}: pronóstico y probabilidad de victoria del Mundial 2026",
        "match_intro": "Probabilidad de victoria de {home} vs {away} (también {away} vs {home}) en el Mundial 2026: {home} {ph}, empate {pd}, {away} {pa}. El resultado más probable es {score}. Del modelo de Probaball: 50 000 simulaciones de Monte Carlo que combinan Elo, cuotas de casas de apuestas y expertos, validado out-of-sample.",
        "faq_h2": "Preguntas frecuentes",
        "faq_q_who": "¿Quién ganará {home} vs {away}?",
        "faq_a_who": "El modelo de Probaball da a {home} un {ph} de probabilidad de victoria, a {away} {pa} y un {pd} de empate.",
        "faq_q_score": "¿Cuál es el resultado más probable?",
        "faq_a_score": "El resultado más probable es {score}.",
        "faq_q_how": "¿Cómo se calcula la probabilidad de victoria?",
        "faq_a_how": "Con 50 000 simulaciones de Monte Carlo que combinan el Elo de los equipos, las cuotas de las casas de apuestas y predicciones de expertos, un modelo validado out-of-sample con resultados pasados.",
        "crumb_home": "Inicio",
        "eval_crumb": "Evaluación",
        "eval_h1": "¿Qué tan acertado es el pronóstico del Mundial 2026?",
        "eval_title": "¿Qué tan acertado es el pronóstico del Mundial 2026? | Probaball",
        "eval_desc": "¿Qué tal va el pronóstico de Probaball para el Mundial 2026? Predicciones previas al partido medidas con el Ranked Probability Score (RPS), con gráfico de calibración y resultados partido a partido.",
        "eval_intro": "Probaball mide sus predicciones previas al partido frente a los resultados reales con el Ranked Probability Score (RPS), la métrica científica estándar para pronósticos de fútbol (Constantinou & Fenton, 2012). Tras {n} partidos de grupos el RPS medio es {rps} (menos es mejor; los modelos de liga publicados rondan 0,19–0,22). El resultado más probable del modelo se ha dado en {called} de {n} partidos, con {upsets} sorpresas hasta ahora.",
        "eval_intro_empty": "Aquí Probaball medirá sus predicciones previas al partido frente a los resultados reales con el Ranked Probability Score (RPS), la métrica científica estándar para pronósticos de fútbol (Constantinou & Fenton, 2012). Vuelve cuando arranque el Mundial 2026.",
    },
    "fr": {
        "wc": "Coupe du monde 2026",
        "group_word": "Groupe",
        "home_h1": "Pronostics Coupe du monde 2026 : qui va gagner ?",
        "home_intro": "Probaball a simulé toute la Coupe du monde 2026 {n} fois, à partir d'un mélange de classements d'équipes (Elo), des principaux bookmakers et de {nexp} experts. Ci-dessous, la probabilité de chaque équipe de devenir championne du monde (données au {date}).",
        "home_h2_champ": "Champion du monde 2026 – probabilités",
        "home_li": "{team} (groupe {g}) – {pct} de gagner la Coupe du monde.",
        "home_h2_teams": "Équipes",
        "home_h2_groups": "Groupes",
        "home_h2_how": "Comment Probaball calcule",
        "home_how1": "Probaball combine plusieurs signaux indépendants en une seule prévision, un peu comme la moyenne de nombreux sondages (un poll of polls). La force de chaque équipe est un mélange pondéré (47,5 % classements, 47,5 % bookmakers, 5 % experts) : un classement Elo calculé sur ~50 000 matchs internationaux (World Football Elo, eloratings.net), des cotes de titre sans marge de {books} (les cotes du marché comptent parmi les prévisions de résultats les plus précises ; Forrest, Goddard & Simmons, 2005) et les pronostics de {nexp} experts. Les matchs sont décidés par un modèle de buts Dixon-Coles dans le tableau final officiel, et tout le tournoi est rejoué {n} fois.",
        "home_how2": "Chaque amélioration du modèle est testée sur des résultats historiques (out-of-sample, Ranked Probability Score; Constantinou & Fenton, 2012) ; ce qui ne prédit pas mieux est abandonné (p. ex. ni le classement FIFA ni un modèle attaque/défense n'apportaient quoi que ce soit). Ce sont des probabilités, pas des certitudes. Probaball n'est ni affilié ni approuvé par la FIFA.",
        "team_h1": "{name} – chances de gagner la Coupe du monde 2026",
        "team_p1": "Selon la simulation data science de Probaball ({n} simulations, données au {date}), {name} a {champ} de chances de gagner la Coupe du monde 2026, {final} d'atteindre la finale, {semi} les demi-finales et {r16} les huitièmes. {name} joue dans le groupe {g}.",
        "team_p2": "La force de l'équipe pondère les classements (Elo), les cotes des bookmakers et les pronostics d'experts (47.5/47.5/5). Au classement FIFA, {name} occupe la place n°{r} sur les 48 équipes du tournoi.",
        "group_link": "Groupe {g}",
        "group_h1": "Groupe {g} – Coupe du monde 2026",
        "group_intro": "Probabilités simulées pour le groupe {g} de la Coupe du monde 2026 (simulation data science, données au {date}) :",
        "group_li": "{team} : gagne le groupe {first}, top 2 {top2}.",
        "home_title": "Pronostics Coupe du monde 2026 : qui va gagner ? | Probaball",
        "home_desc": "Mis à jour chaque jour après chaque match. Pronostics de la Coupe du monde 2026 : qui va gagner, les chances de titre de chaque équipe et un pronostic pour chaque match, sur 50 000 simulations.",
        "home_updated": "Mis à jour chaque jour · pronostic {date} · {played} matchs sur {total} joués",
        "home_h2_matches": "Pronostics des matchs de la Coupe du monde",
        "home_matches_intro": "La probabilité de victoire du modèle pour chaque match, mise à jour après chaque résultat.",
        "home_upcoming": "Prochains matchs",
        "home_results": "Résultats récents vs notre pronostic",
        "home_vs": "-",
        "home_draw": "Nul",
        "home_called": "comme prévu",
        "home_upset": "surprise",
        "home_all_results": "Tous les résultats et la fiabilité",
        "home_bracket_link": "Tous les pronostics du tableau",
        "bracket_crumb": "Tableau final",
        "bracket_h1": "Pronostics du tableau de la Coupe du monde 2026",
        "bracket_title": "Tableau Coupe du monde 2026 : pronostics & probabilités | Probaball",
        "bracket_desc": "Mis à jour chaque jour. Pronostics du tableau final de la Coupe du monde 2026 : les chances de chaque équipe d'atteindre les 8es, quarts, demi-finale, finale et de gagner le titre, sur 50 000 simulations.",
        "bracket_intro": "Les chances de chaque équipe d'atteindre chaque tour à élimination directe de la Coupe du monde 2026, sur {n} simulations (données au {date}). Les affiches se figent à la fin de la phase de groupes : les pronostics match par match arrivent alors.",
        "br_win": "Titre", "br_final": "Finale", "br_sf": "Demies", "br_qf": "Quarts", "br_r16": "8es",
        "team_title": "{name} – chances de gagner la Coupe du monde 2026 | Probaball",
        "team_desc": "{name} : {champ} de gagner la Coupe du monde 2026, {final} en finale. Probabilités issues des classements, bookmakers et experts.",
        "group_title": "Groupe {g} – Coupe du monde 2026 | Probaball",
        "group_desc": "Groupe {g} de la Coupe du monde 2026 : probabilités simulées de qualification de chaque équipe.",
        "match_title": "{home} - {away} : pronostic & probabilité | Coupe du monde 2026",
        "match_desc": "Probabilité de victoire {home} - {away} à la Coupe du monde 2026 : {home} {ph}, nul {pd}, {away} {pa}. Score le plus probable {score}, selon le modèle Probaball (50 000 simulations).",
        "match_h1": "{home} - {away} : pronostic & probabilité de victoire à la Coupe du monde 2026",
        "match_intro": "Probabilité de victoire pour {home} - {away} (aussi {away} - {home}) à la Coupe du monde 2026 : {home} {ph}, nul {pd}, {away} {pa}. Le score le plus probable est {score}. D'après le modèle Probaball — 50 000 simulations de Monte Carlo combinant Elo, cotes des bookmakers et experts, validé hors échantillon.",
        "faq_h2": "Questions fréquentes",
        "faq_q_who": "Qui va gagner {home} - {away} ?",
        "faq_a_who": "Le modèle Probaball donne à {home} une probabilité de victoire de {ph}, à {away} {pa}, et {pd} de match nul.",
        "faq_q_score": "Quel est le score le plus probable ?",
        "faq_a_score": "Le score le plus probable est {score}.",
        "faq_q_how": "Comment la probabilité de victoire est-elle calculée ?",
        "faq_a_how": "À partir de 50 000 simulations de Monte Carlo combinant les classements Elo des équipes, les cotes des bookmakers et les pronostics d'experts — un modèle validé hors échantillon sur les résultats passés.",
        "crumb_home": "Accueil",
        "eval_crumb": "Évaluation",
        "eval_h1": "Quelle est la fiabilité du pronostic de la Coupe du monde 2026 ?",
        "eval_title": "Fiabilité du pronostic de la Coupe du monde 2026 | Probaball",
        "eval_desc": "Quelle est la performance du pronostic de Probaball pour la Coupe du monde 2026 ? Pronostics d'avant-match évalués avec le Ranked Probability Score (RPS), avec graphique de calibrage et résultats match par match.",
        "eval_intro": "Probaball confronte ses pronostics d'avant-match aux résultats réels à l'aide du Ranked Probability Score (RPS), la métrique scientifique de référence pour les pronostics de football (Constantinou & Fenton, 2012). Après {n} matchs de poule, le RPS moyen est de {rps} (plus bas est meilleur ; les modèles de club publiés tournent autour de 0,19–0,22). Le résultat le plus probable du modèle s'est produit dans {called} matchs sur {n}, avec {upsets} surprises jusqu'ici.",
        "eval_intro_empty": "Ici, Probaball confrontera ses pronostics d'avant-match aux résultats réels à l'aide du Ranked Probability Score (RPS), la métrique scientifique de référence pour les pronostics de football (Constantinou & Fenton, 2012). Revenez une fois la Coupe du monde 2026 lancée.",
    },
    "pt": {
        "wc": "Copa do Mundo 2026",
        "group_word": "Grupo",
        "home_h1": "Prognósticos da Copa do Mundo 2026: quem vai ganhar?",
        "home_intro": "A Probaball simulou toda a Copa do Mundo 2026 {n} vezes, a partir de uma mistura de rankings de seleções (Elo), as principais casas de apostas e {nexp} especialistas. Abaixo está a probabilidade de cada seleção ser campeã mundial (dados de {date}).",
        "home_h2_champ": "Campeã mundial 2026 – probabilidades",
        "home_li": "{team} (grupo {g}) – {pct} de ganhar a Copa.",
        "home_h2_teams": "Seleções",
        "home_h2_groups": "Grupos",
        "home_h2_how": "Como a Probaball calcula",
        "home_how1": "A Probaball combina vários sinais independentes em uma única previsão, parecido com a média de muitas pesquisas (um poll of polls). A força de cada seleção é uma mistura ponderada (47,5 % rankings, 47,5 % casas de apostas, 5 % especialistas): um rating Elo calculado sobre ~50 000 jogos internacionais (World Football Elo, eloratings.net), odds de título sem margem de {books} (as odds de mercado estão entre as previsões de resultados mais precisas; Forrest, Goddard & Simmons, 2005) e previsões de {nexp} especialistas. As partidas são decididas por um modelo de gols Dixon-Coles no mata-mata oficial, e todo o torneio é jogado {n} vezes.",
        "home_how2": "Cada melhoria do modelo é testada contra resultados históricos (out-of-sample, Ranked Probability Score; Constantinou & Fenton, 2012); o que não acerta melhor é descartado (por ex., nem o ranking FIFA nem um modelo de ataque/defesa acrescentaram nada). São probabilidades, não certezas. A Probaball não é afiliada nem endossada pela FIFA.",
        "team_h1": "{name} – chance de ganhar a Copa do Mundo 2026",
        "team_p1": "Segundo a simulação de data science da Probaball ({n} simulações, dados de {date}), {name} tem {champ} de chance de ganhar a Copa do Mundo 2026, {final} de chegar à final, {semi} às semifinais e {r16} às oitavas. {name} joga no grupo {g}.",
        "team_p2": "A força da seleção pondera rankings (Elo), odds de apostas e previsões de especialistas (47.5/47.5/5). No ranking FIFA, {name} está em #{r} das 48 seleções do torneio.",
        "group_link": "Grupo {g}",
        "group_h1": "Grupo {g} – Copa do Mundo 2026",
        "group_intro": "Probabilidades simuladas para o grupo {g} da Copa do Mundo 2026 (simulação de data science, dados de {date}):",
        "group_li": "{team}: vence o grupo {first}, top 2 {top2}.",
        "home_title": "Prognósticos Copa do Mundo 2026: quem vai ganhar? | Probaball",
        "home_desc": "Atualizado todos os dias após cada jogo. Prognósticos da Copa do Mundo 2026: quem vai ganhar, a chance de título de cada seleção e um prognóstico para cada jogo, de 50 000 simulações.",
        "home_updated": "Atualizado todos os dias · prognóstico {date} · {played} de {total} jogos disputados",
        "home_h2_matches": "Prognósticos dos jogos da Copa",
        "home_matches_intro": "A probabilidade de vitória do modelo para cada jogo, atualizada após cada resultado.",
        "home_upcoming": "Próximos jogos",
        "home_results": "Resultados recentes vs o nosso prognóstico",
        "home_vs": "x",
        "home_draw": "Empate",
        "home_called": "como previsto",
        "home_upset": "zebra",
        "home_all_results": "Todos os resultados e acerto",
        "home_bracket_link": "Todos os prognósticos do mata-mata",
        "bracket_crumb": "Mata-mata",
        "bracket_h1": "Prognósticos do mata-mata da Copa do Mundo 2026",
        "bracket_title": "Mata-mata da Copa 2026: prognósticos e probabilidades | Probaball",
        "bracket_desc": "Atualizado todos os dias. Prognósticos do mata-mata da Copa do Mundo 2026: a chance de cada seleção chegar às oitavas, quartas, semifinal, final e ganhar o título, de 50 000 simulações.",
        "bracket_intro": "A chance de cada seleção alcançar cada fase do mata-mata da Copa do Mundo 2026, de {n} simulações (dados de {date}). Os confrontos são definidos ao fim da fase de grupos: então saem os prognósticos jogo a jogo.",
        "br_win": "Título", "br_final": "Final", "br_sf": "Semis", "br_qf": "Quartas", "br_r16": "Oitavas",
        "team_title": "{name} – chance de ganhar a Copa do Mundo 2026 | Probaball",
        "team_desc": "{name}: {champ} de ganhar a Copa do Mundo 2026, {final} à final. Probabilidades de rankings, casas de apostas e especialistas.",
        "group_title": "Grupo {g} – Copa do Mundo 2026 | Probaball",
        "group_desc": "Grupo {g} da Copa do Mundo 2026: probabilidades simuladas de cada seleção avançar da fase de grupos.",
        "match_title": "{home} x {away}: prognóstico e probabilidade | Copa do Mundo 2026",
        "match_desc": "Probabilidade de vitória {home} x {away} na Copa do Mundo 2026: {home} {ph}, empate {pd}, {away} {pa}. Resultado mais provável {score}, do modelo da Probaball (50 000 simulações).",
        "match_h1": "{home} x {away}: prognóstico e probabilidade de vitória da Copa do Mundo 2026",
        "match_intro": "Probabilidade de vitória de {home} x {away} (também {away} x {home}) na Copa do Mundo 2026: {home} {ph}, empate {pd}, {away} {pa}. O resultado mais provável é {score}. Do modelo da Probaball — 50 000 simulações de Monte Carlo combinando Elo, odds de casas de apostas e especialistas, validado fora da amostra.",
        "faq_h2": "Perguntas frequentes",
        "faq_q_who": "Quem vai ganhar {home} x {away}?",
        "faq_a_who": "O modelo da Probaball dá a {home} {ph} de probabilidade de vitória, a {away} {pa} e {pd} de empate.",
        "faq_q_score": "Qual é o resultado mais provável?",
        "faq_a_score": "O resultado mais provável é {score}.",
        "faq_q_how": "Como a probabilidade de vitória é calculada?",
        "faq_a_how": "A partir de 50 000 simulações de Monte Carlo combinando o Elo das seleções, odds de casas de apostas e previsões de especialistas — um modelo validado fora da amostra com resultados passados.",
        "crumb_home": "Início",
        "eval_crumb": "Avaliação",
        "eval_h1": "Quão acertada é a previsão do Mundial 2026?",
        "eval_title": "Quão acertada é a previsão do Mundial 2026? | Probaball",
        "eval_desc": "Como vai a previsão da Probaball para o Mundial 2026? Previsões antes do jogo medidas com o Ranked Probability Score (RPS), com gráfico de calibração e resultados jogo a jogo.",
        "eval_intro": "A Probaball mede as suas previsões antes do jogo face aos resultados reais com o Ranked Probability Score (RPS), a métrica científica padrão para previsões de futebol (Constantinou & Fenton, 2012). Após {n} jogos da fase de grupos, o RPS médio é {rps} (menor é melhor; os modelos de liga publicados rondam 0,19–0,22). O resultado mais provável do modelo ocorreu em {called} de {n} jogos, com {upsets} surpresas até agora.",
        "eval_intro_empty": "Aqui a Probaball irá medir as suas previsões antes do jogo face aos resultados reais com o Ranked Probability Score (RPS), a métrica científica padrão para previsões de futebol (Constantinou & Fenton, 2012). Volta quando o Mundial 2026 começar.",
    },
    "de": {
        "wc": "Fußball-WM 2026",
        "group_word": "Gruppe",
        "home_h1": "Fußball-WM 2026: Prognosen – wer gewinnt?",
        "home_intro": "Probaball hat die gesamte Fußball-WM 2026 {n} Mal simuliert, auf Basis einer Mischung aus Team-Rankings (Elo), führenden Buchmachern und {nexp} Experten. Unten steht die Wahrscheinlichkeit jedes Teams, Weltmeister zu werden (Daten vom {date}).",
        "home_h2_champ": "Weltmeister 2026 – Wahrscheinlichkeiten",
        "home_li": "{team} (Gruppe {g}) – {pct}, die WM zu gewinnen.",
        "home_h2_teams": "Teams",
        "home_h2_groups": "Gruppen",
        "home_h2_how": "So rechnet Probaball",
        "home_how1": "Probaball fasst mehrere unabhängige Signale zu einer Prognose zusammen – ähnlich wie der Durchschnitt vieler Umfragen (ein poll of polls). Die Stärke jedes Teams ist eine gewichtete Mischung (47,5 % Rankings, 47,5 % Buchmacher, 5 % Experten): eine Elo-Wertung aus ~50 000 Länderspielen (World Football Elo, eloratings.net), margenbereinigte Titelquoten von {books} (Marktquoten zählen zu den treffsichersten Ergebnisprognosen; Forrest, Goddard & Simmons, 2005) und Prognosen von {nexp} Experten. Die Spiele werden mit einem Dixon-Coles-Tormodell im offiziellen K.-o.-Baum entschieden, und das ganze Turnier wird {n} Mal durchgespielt.",
        "home_how2": "Jede Modellverbesserung wird an historischen Ergebnissen getestet (out-of-sample, Ranked Probability Score; Constantinou & Fenton, 2012); was nicht besser trifft, fliegt raus (z. B. brachten weder das FIFA-Ranking noch ein Angriffs-/Abwehrmodell etwas). Das sind Wahrscheinlichkeiten, keine Gewissheiten. Probaball ist nicht mit der FIFA verbunden oder von ihr unterstützt.",
        "team_h1": "{name} – Chance auf den WM-Titel 2026",
        "team_p1": "Laut Probaballs Data-Science-Simulation ({n} Simulationen, Daten vom {date}) hat {name} {champ} Chance, die WM 2026 zu gewinnen, {final} das Finale zu erreichen, {semi} das Halbfinale und {r16} das Achtelfinale. {name} spielt in Gruppe {g}.",
        "team_p2": "Die Stärke des Teams gewichtet Rankings (Elo), Buchmacherquoten und Expertenprognosen (47.5/47.5/5). Im FIFA-Ranking liegt {name} auf Platz #{r} der 48 Teams im Turnier.",
        "group_link": "Gruppe {g}",
        "group_h1": "Gruppe {g} – Fußball-WM 2026",
        "group_intro": "Simulierte Wahrscheinlichkeiten für Gruppe {g} bei der Fußball-WM 2026 (Data-Science-Simulation, Daten vom {date}):",
        "group_li": "{team}: gewinnt die Gruppe {first}, Top 2 {top2}.",
        "home_title": "WM 2026 Prognosen: Wer gewinnt? Quoten | Probaball",
        "home_desc": "Täglich nach jedem Spiel aktualisiert. Prognosen zur Fußball-WM 2026: wer gewinnt, die Titelchance jedes Teams und eine Prognose für jedes Spiel, aus 50 000 Simulationen.",
        "home_updated": "Täglich aktualisiert · Prognose {date} · {played} von {total} Spielen gespielt",
        "home_h2_matches": "WM-Spiele: Prognosen",
        "home_matches_intro": "Die Siegwahrscheinlichkeit des Modells für jedes Spiel, nach jedem Ergebnis aktualisiert.",
        "home_upcoming": "Kommende Spiele",
        "home_results": "Letzte Ergebnisse vs. unsere Prognose",
        "home_vs": "-",
        "home_draw": "Unentschieden",
        "home_called": "wie vorhergesagt",
        "home_upset": "Überraschung",
        "home_all_results": "Alle Ergebnisse & Trefferquote",
        "home_bracket_link": "Alle K.-o.-Prognosen",
        "bracket_crumb": "K.-o.-Runde",
        "bracket_h1": "Fußball-WM 2026: K.-o.-Runde – Prognosen",
        "bracket_title": "WM 2026 K.-o.-Runde: Prognosen & Wahrscheinlichkeiten | Probaball",
        "bracket_desc": "Täglich aktualisiert. Prognosen zur K.-o.-Runde der Fußball-WM 2026: die Chance jedes Teams aufs Achtelfinale, Viertelfinale, Halbfinale, Finale und den Titel, aus 50 000 Simulationen.",
        "bracket_intro": "Die Chance jedes Teams, jede K.-o.-Runde der Fußball-WM 2026 zu erreichen, aus {n} Simulationen (Stand {date}). Die Paarungen stehen nach der Gruppenphase fest – dann gehen die Prognosen Spiel für Spiel live.",
        "br_win": "Titel", "br_final": "Finale", "br_sf": "Halbf.", "br_qf": "Viertelf.", "br_r16": "Achtelf.",
        "team_title": "{name} – Chance auf den WM-Titel 2026 | Probaball",
        "team_desc": "{name}: {champ} Titelchance bei der WM 2026, {final} ins Finale. Wahrscheinlichkeiten aus Rankings, Buchmachern und Experten.",
        "group_title": "Gruppe {g} – Fußball-WM 2026 | Probaball",
        "group_desc": "Gruppe {g} bei der WM 2026: simulierte Wahrscheinlichkeiten für das Weiterkommen jedes Teams.",
        "match_title": "{home} - {away}: Prognose & Siegwahrscheinlichkeit | WM 2026",
        "match_desc": "Siegwahrscheinlichkeit {home} - {away} bei der Fußball-WM 2026: {home} {ph}, Unentschieden {pd}, {away} {pa}. Wahrscheinlichstes Ergebnis {score}, aus Probaballs Modell (50 000 Simulationen).",
        "match_h1": "{home} - {away}: Prognose & Siegwahrscheinlichkeit zur Fußball-WM 2026",
        "match_intro": "Siegwahrscheinlichkeit für {home} - {away} (auch {away} - {home}) bei der Fußball-WM 2026: {home} {ph}, Unentschieden {pd}, {away} {pa}. Das wahrscheinlichste Ergebnis ist {score}. Aus Probaballs Modell — 50 000 Monte-Carlo-Simulationen aus Elo, Buchmacherquoten und Experten, out-of-sample validiert.",
        "faq_h2": "Häufige Fragen",
        "faq_q_who": "Wer gewinnt {home} - {away}?",
        "faq_a_who": "Probaballs Modell gibt {home} eine Siegwahrscheinlichkeit von {ph}, {away} {pa} und {pd} für ein Unentschieden.",
        "faq_q_score": "Was ist das wahrscheinlichste Ergebnis?",
        "faq_a_score": "Das wahrscheinlichste Ergebnis ist {score}.",
        "faq_q_how": "Wie wird die Siegwahrscheinlichkeit berechnet?",
        "faq_a_how": "Aus 50 000 Monte-Carlo-Simulationen, die Elo-Ratings der Teams, Buchmacherquoten und Expertenprognosen kombinieren — ein Modell, das out-of-sample an früheren Ergebnissen validiert wurde.",
        "crumb_home": "Start",
        "eval_crumb": "Auswertung",
        "eval_h1": "Wie treffsicher ist die WM-Prognose 2026?",
        "eval_title": "Wie treffsicher ist die WM-Prognose 2026? | Probaball",
        "eval_desc": "Wie gut liegt Probaballs WM-Prognose 2026? Vorhersagen vor dem Spiel, bewertet mit dem Ranked Probability Score (RPS), mit Kalibrierungsdiagramm und Ergebnissen Spiel für Spiel.",
        "eval_intro": "Probaball misst seine Vorhersagen vor dem Spiel an den tatsächlichen Ergebnissen mit dem Ranked Probability Score (RPS) – der wissenschaftlichen Standardmetrik für Fußballprognosen (Constantinou & Fenton, 2012). Nach {n} Gruppenspielen liegt der durchschnittliche RPS bei {rps} (niedriger ist besser; veröffentlichte Ligamodelle liegen bei etwa 0,19–0,22). Der wahrscheinlichste Ausgang des Modells trat in {called} von {n} Spielen ein, mit bislang {upsets} Überraschungen.",
        "eval_intro_empty": "Hier misst Probaball seine Vorhersagen vor dem Spiel an den tatsächlichen Ergebnissen mit dem Ranked Probability Score (RPS) – der wissenschaftlichen Standardmetrik für Fußballprognosen (Constantinou & Fenton, 2012). Schau wieder vorbei, sobald die WM 2026 läuft.",
    },
}


# ----------------------------------------------------------------------
# URL + output-path helpers (Swedish at root, others under /<lang>/).
# ----------------------------------------------------------------------
def url_for(lang, route):
    prefix = "" if lang == ROOT_LANG else f"/{lang}"
    return f"{ORIGIN}{prefix}/" if route == "/" else f"{ORIGIN}{prefix}{route}"


def out_path(base, lang, route):
    parts = [base]
    if lang != ROOT_LANG:
        parts.append(lang)
    sub = route.strip("/")
    if sub:
        parts.append(sub)
    return os.path.join(*parts, "index.html")


def load_team_names():
    """Localized team names keyed by Swedish team name, per language.

    Single source of truth is the SPA's TEAM_NAMES in src/i18n.jsx — parse it
    here so SSR titles/H1s/prose use the names searchers actually type (e.g.
    'Cabo Verde', 'Sénégal', 'Türkei') instead of falling back to English.
    Returns {} on any parse failure, in which case team_name() falls back to
    name_en (the previous behavior)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "i18n.jsx")
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return {}
    m = re.search(r"export const TEAM_NAMES\s*=\s*\{(.*?)\n\};", text, re.DOTALL)
    if not m:
        return {}
    out = {}
    for lm in re.finditer(r"(\w+)\s*:\s*\{([^}]*)\}", m.group(1)):
        names = {}
        for pm in re.finditer(r'(?:"([^"]+)"|(\w+))\s*:\s*"([^"]+)"', lm.group(2)):
            key = pm.group(1) if pm.group(1) is not None else pm.group(2)
            names[key] = pm.group(3)
        out[lm.group(1)] = names
    return out


TEAM_NAMES = load_team_names()


def team_name(t, lang):
    if lang == "sv":
        return t["team"]
    loc = TEAM_NAMES.get(lang, {}).get(t["team"])
    return loc or t.get("name_en", t["team"])


# ----------------------------------------------------------------------
# Fragments (server-rendered, localized prose inside #root).
# ----------------------------------------------------------------------
TOTAL_MATCHES = 104  # 48-team format: 72 group + 32 knockout


def home_match_section(tr, lang, d, teams):
    """Dated, crawlable list of upcoming match predictions + recent results vs
    our forecast. Captures match-level + 'today' search intent, links every
    match page (internal-link equity they otherwise lack), and refreshes daily."""
    gm = d.get("group_matches") or {}
    all_m = sorted((m for ms in gm.values() for m in ms),
                   key=lambda m: (m["date"], m.get("matchday", 0)))
    if not all_m:
        return []
    en_map = {t["team"]: t.get("name_en", t["team"]) for t in teams}

    def loc(sv):
        return sv if lang == "sv" else (TEAM_NAMES.get(lang, {}).get(sv) or en_map.get(sv, sv))

    def murl(m):
        s = slugify(en_map.get(m["home"], m["home"])) + "-vs-" + slugify(en_map.get(m["away"], m["away"]))
        return url_for(lang, "/match/" + s + "/")

    vs = tr["home_vs"]
    upcoming = [m for m in all_m if m.get("result") is None][:8]
    recent = [m for m in all_m if m.get("result") is not None][-6:][::-1]
    out = [f"<h2>{esc(tr['home_h2_matches'])}</h2>",
           f"<p>{esc(tr['home_matches_intro'])}</p>"]
    if upcoming:
        out.append(f"<h3>{esc(tr['home_upcoming'])}</h3><ul>")
        for m in upcoming:
            opts = [("h", m["p_home"]), ("d", m["p_draw"]), ("a", m["p_away"])]
            who, p = max(opts, key=lambda x: x[1])
            fav = tr["home_draw"] if who == "d" else loc(m["home"] if who == "h" else m["away"])
            matchup = f"{loc(m['home'])} {vs} {loc(m['away'])}"
            out.append(f'<li><a href="{murl(m)}">{esc(matchup)}</a> — '
                       f"{esc(fav)} {pct(p, lang)}</li>")
        out.append("</ul>")
    if recent:
        out.append(f"<h3>{esc(tr['home_results'])}</h3><ul>")
        for m in recent:
            r = m["result"]
            mark, lbl = ("✓", tr["home_called"]) if m.get("as_predicted") else ("✗", tr["home_upset"])
            score = f"{loc(m['home'])} {r['home']}–{r['away']} {loc(m['away'])}"
            out.append(f'<li><a href="{murl(m)}">{esc(score)}</a> '
                       f'<span title="{esc(lbl)}">{mark}</span></li>')
        out.append("</ul>")
    out.append(f'<p><a href="{url_for(lang, "/evaluation/")}">'
               f'{esc(tr["home_all_results"])} →</a></p>')
    return out


def home_fragment(tr, lang, d, teams, groups):
    n = fmt_n(d.get("n", 0), lang)
    date = esc(d.get("date", ""))
    played = (d.get("tournament") or {}).get("n_played") \
        or (d.get("evaluation") or {}).get("n") or 0
    model = d.get("model") or {}
    books = ", ".join(model.get("books", [])) or "ledande oddsmakare"
    nexp = model.get("num_experts", 0)
    gw = tr["group_word"]
    lines = [
        '<main id="ssr-content">',
        f"<h1>{esc(tr['home_h1'])}</h1>",
        "<p>" + esc(tr["home_updated"].format(date=date, played=played, total=TOTAL_MATCHES)) + "</p>",
        "<p>" + esc(tr["home_intro"].format(n=n, nexp=nexp, date=date)) + "</p>",
        f"<h2>{esc(tr['home_h2_champ'])}</h2>",
        "<ol>",
    ]
    for t in teams[:24]:
        slug = slugify(t["name_en"])
        name = team_name(t, lang)
        # Render the team name as a link, then the rest of the sentence. The
        # {team} placeholder leads every home_li template, so split on a sentinel.
        rest = tr["home_li"].format(team="\x00", g=t["group"],
                                    pct=pct(t["champion"], lang)).split("\x00", 1)[1]
        url = url_for(lang, "/lag/" + slug + "/")
        lines.append(f'<li><a href="{url}">{esc(name)}</a>{esc(rest)}</li>')
    lines.append("</ol>")
    lines.append(f'<p><a href="{url_for(lang, "/bracket/")}">'
                 f'{esc(tr["home_bracket_link"])} →</a></p>')
    lines += home_match_section(tr, lang, d, teams)

    def team_link(t):
        url = url_for(lang, "/lag/" + slugify(t["name_en"]) + "/")
        return f'<a href="{url}">{esc(team_name(t, lang))}</a>'

    def group_link(g):
        url = url_for(lang, "/grupp/" + g.lower() + "/")
        return f'<a href="{url}">{gw} {esc(g)}</a>'

    lines.append(f"<h2>{esc(tr['home_h2_teams'])}</h2><p>" + " · ".join(
        team_link(t) for t in sorted(teams, key=lambda x: team_name(x, lang))) + "</p>")
    lines.append(f"<h2>{esc(tr['home_h2_groups'])}</h2><p>" + " · ".join(
        group_link(g) for g in sorted(groups)) + "</p>")
    lines += [
        f"<h2>{esc(tr['home_h2_how'])}</h2>",
        "<p>" + esc(tr["home_how1"].format(books=books, nexp=nexp, n=n)) + "</p>",
        "<p>" + esc(tr["home_how2"]) + "</p>",
        "</main>",
    ]
    return "\n".join(lines)


def team_fragment(tr, lang, t, n_raw, date):
    name = team_name(t, lang)
    g = t["group"]
    n = fmt_n(n_raw, lang)
    p1 = tr["team_p1"].format(n=n, date=esc(date), name=esc(name),
                              champ=pct(t["champion"], lang), final=pct(t["final"], lang),
                              semi=pct(t["semi"], lang), r16=pct(t["r16"], lang), g=esc(g))
    p2 = tr["team_p2"].format(name=esc(name), r=t.get("fifa_field_rank", "?"))
    home_url = url_for(lang, "/")
    group_url = url_for(lang, "/grupp/" + g.lower() + "/")
    group_label = esc(tr["group_link"].format(g=g))
    h1 = esc(tr["team_h1"].format(name=name))
    return "\n".join([
        '<main id="ssr-content">',
        f'<p><a href="{home_url}">← Probaball</a></p>',
        f"<h1>{h1}</h1>",
        f"<p>{p1}</p>",
        f"<p>{p2}</p>",
        f'<p><a href="{group_url}">{group_label}</a></p>',
        "</main>",
    ])


def group_fragment(tr, lang, g, rows, date):
    def li(r):
        name = r["team"] if lang == "sv" else (
            TEAM_NAMES.get(lang, {}).get(r["team"]) or r["team_en"])
        rest = tr["group_li"].format(team="\x00", first=pct(r["p_first"], lang),
                                     top2=pct(r["p_first"] + r["p_second"], lang)).split("\x00", 1)[1]
        url = url_for(lang, "/lag/" + slugify(r["team_en"]) + "/")
        return f'<li><a href="{url}">{esc(name)}</a>{esc(rest)}</li>'
    items = "".join(li(r) for r in rows)
    return "\n".join([
        '<main id="ssr-content">',
        f'<p><a href="{url_for(lang, "/")}">← Probaball</a></p>',
        f"<h1>{esc(tr['group_h1'].format(g=g))}</h1>",
        f"<p>{esc(tr['group_intro'].format(g=g, date=esc(date)))}</p>",
        f"<ul>{items}</ul>",
        "</main>",
    ])


def rps_fmt(v, lang):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") if lang in DECIMAL_COMMA else s


def eval_fragment(tr, lang, d):
    ev = d.get("evaluation") or {}
    home_url = url_for(lang, "/")
    if ev.get("n"):
        intro = tr["eval_intro"].format(
            n=ev["n"], rps=rps_fmt(ev["mean_rps"], lang),
            called=ev["n_called"], upsets=ev["n_upset"])
    else:
        intro = tr["eval_intro_empty"]
    return "\n".join([
        '<main id="ssr-content">',
        f'<p><a href="{home_url}">← Probaball</a></p>',
        f"<h1>{esc(tr['eval_h1'])}</h1>",
        f"<p>{esc(intro)}</p>",
        "</main>",
    ])


def match_vars(tr, lang, m, g, en):
    """Shared {placeholders} for a match's title/desc/intro."""
    # Localized team name from a Swedish key — mirrors team_name(): prefer the
    # per-language TEAM_NAMES, fall back to English, then the Swedish key.
    name = lambda sv: sv if lang == "sv" else (
        TEAM_NAMES.get(lang, {}).get(sv) or en.get(sv, sv))
    return {
        "home": name(m["home"]), "away": name(m["away"]),
        "ph": pct(m["p_home"], lang), "pd": pct(m["p_draw"], lang),
        "pa": pct(m["p_away"], lang), "score": f"{m['hg']}–{m['ag']}",
        "g": g, "md": m["matchday"],
    }


def match_faq_pairs(tr, v):
    """(question, answer) pairs for a match page, from the model's numbers —
    targets the 'Who will win X vs Y?' People-Also-Ask cluster."""
    pairs = [("faq_q_who", "faq_a_who"), ("faq_q_score", "faq_a_score"),
             ("faq_q_how", "faq_a_how")]
    return [(tr[q].format(**v), tr[a].format(**v)) for q, a in pairs]


def faq_ld(pairs):
    return {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in pairs
        ],
    }


def match_fragment(tr, lang, m, g, en):
    v = match_vars(tr, lang, m, g, en)
    home_url = url_for(lang, "/lag/" + slugify(en.get(m["home"], m["home"])) + "/")
    away_url = url_for(lang, "/lag/" + slugify(en.get(m["away"], m["away"])) + "/")
    group_url = url_for(lang, "/grupp/" + g.lower() + "/")
    lines = [
        '<main id="ssr-content">',
        f'<p><a href="{url_for(lang, "/")}">← Probaball</a></p>',
        f"<h1>{esc(tr['match_h1'].format(**v))}</h1>",
        f"<p>{esc(tr['match_intro'].format(**v))}</p>",
        f'<p><a href="{home_url}">{esc(v["home"])}</a> · '
        f'<a href="{group_url}">{esc(tr["group_link"].format(g=g))}</a> · '
        f'<a href="{away_url}">{esc(v["away"])}</a></p>',
        f"<h2>{esc(tr['faq_h2'])}</h2>",
    ]
    for q, a in match_faq_pairs(tr, v):
        lines.append(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>")
    lines.append("</main>")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Head injection: title / desc / canonical / <html lang> / OG / hreflang /
# breadcrumb JSON-LD.
# ----------------------------------------------------------------------
def bracket_fragment(tr, lang, d, teams):
    """Knockout-stage odds: each team's chance to reach each round, from data we
    have today (per-team r16/quarter/semi/final/champion). The actual knockout
    fixtures aren't known until the group stage ends; this links all 48 team
    pages and targets 'World Cup bracket' search demand meanwhile."""
    date = esc(d.get("date", ""))
    n = fmt_n(d.get("n", 0), lang)
    played = (d.get("tournament") or {}).get("n_played") \
        or (d.get("evaluation") or {}).get("n") or 0
    head = (f"<th>{esc(tr['br_win'])}</th><th>{esc(tr['br_final'])}</th>"
            f"<th>{esc(tr['br_sf'])}</th><th>{esc(tr['br_qf'])}</th><th>{esc(tr['br_r16'])}</th>")
    body = []
    for t in sorted(teams, key=lambda x: -x.get("champion", 0)):
        url = url_for(lang, "/lag/" + slugify(t["name_en"]) + "/")
        cells = "".join(f"<td>{pct(t.get(k, 0), lang)}</td>"
                        for k in ("champion", "final", "semi", "quarter", "r16"))
        body.append(f'<tr><td><a href="{url}">{esc(team_name(t, lang))}</a></td>{cells}</tr>')
    return "\n".join([
        '<main id="ssr-content">',
        f'<p><a href="{url_for(lang, "/")}">← Probaball</a></p>',
        f"<h1>{esc(tr['bracket_h1'])}</h1>",
        "<p>" + esc(tr["home_updated"].format(date=date, played=played, total=TOTAL_MATCHES)) + "</p>",
        "<p>" + esc(tr["bracket_intro"].format(n=n, date=date)) + "</p>",
        f"<table><thead><tr><th>{esc(tr['home_h2_teams'])}</th>{head}</tr></thead><tbody>",
        *body,
        "</tbody></table>",
        f'<p><a href="{url_for(lang, "/evaluation/")}">{esc(tr["home_all_results"])} →</a></p>',
        "</main>",
    ])


# "Open source" page — SSR prose + meta, per language. The model + this app are
# published to a public GitHub mirror; this page targets transparency/"open
# model" demand and links there. Keep REPO_URL in sync with frontend/src/
# components/CodeModal.jsx.
REPO_URL = "https://github.com/perkarlberg/probaball-open"
CODE_T = {
    "en": {
        "title": "Open source — the model and this site are open | Probaball",
        "desc": "Probaball's whole World Cup 2026 forecast is open source under the MIT license: data ingestion, the Monte Carlo model, the backtest, and this web app. View the code on GitHub.",
        "crumb": "Open source", "h1": "Probaball is open source",
        "lede": "A forecast is only as trustworthy as it is transparent. So the whole of Probaball — the data, the model, the simulation and this web app — is open source under the MIT license. Inspect it, question it, reuse it.",
        "cta": "View the code on GitHub →", "what_h": "What's in the repo",
        "what": ["Data ingestion — Elo from ~50,000 internationals, bookmaker title odds and expert picks, blended into each team's strength.",
                 "The model — a Monte Carlo engine that plays the 48-team tournament out tens of thousands of times.",
                 "Backtest & calibration — out-of-sample scoring (RPS) that referees every model change.",
                 "The web app — this site (React + Vite), in six languages."],
        "data_h": "Data & license",
        "data": "Built on open and public sources. MIT-licensed. A statistical forecast, not a prediction — and not affiliated with or endorsed by FIFA.",
    },
    "sv": {
        "title": "Öppen källkod — modellen och sajten är öppna | Probaball",
        "desc": "Hela Probaballs VM 2026-prognos är öppen källkod under MIT-licens: datainsamling, Monte Carlo-modellen, backtestet och webappen. Se koden på GitHub.",
        "crumb": "Öppen källkod", "h1": "Probaball är öppen källkod",
        "lede": "En prognos är bara så trovärdig som den är genomskinlig. Därför är hela Probaball — datan, modellen, simuleringen och den här webappen — öppen källkod under MIT-licens. Granska den, ifrågasätt den, återanvänd den.",
        "cta": "Se koden på GitHub →", "what_h": "Vad finns i repot",
        "what": ["Datainsamling — Elo från ~50 000 landskamper, vinnarodds och experttips, sammanvägt till varje lags styrka.",
                 "Modellen — en Monte Carlo-motor som spelar upp turneringen med 48 lag tiotusentals gånger.",
                 "Backtest & kalibrering — out-of-sample-mått (RPS) som dömer varje modelländring.",
                 "Webappen — den här sajten (React + Vite), på sex språk."],
        "data_h": "Data & licens",
        "data": "Bygger på öppna och offentliga källor. MIT-licens. En statistisk prognos, inte en spådom — och inte ansluten till eller godkänd av FIFA.",
    },
    "es": {
        "title": "Código abierto — el modelo y este sitio son abiertos | Probaball",
        "desc": "Toda la predicción del Mundial 2026 de Probaball es de código abierto con licencia MIT: ingesta de datos, el modelo Monte Carlo, el backtest y esta web. Ver el código en GitHub.",
        "crumb": "Código abierto", "h1": "Probaball es de código abierto",
        "lede": "Una predicción solo es tan fiable como transparente. Por eso todo Probaball — los datos, el modelo, la simulación y esta web — es de código abierto con licencia MIT. Examínalo, cuestiónalo, reutilízalo.",
        "cta": "Ver el código en GitHub →", "what_h": "Qué hay en el repositorio",
        "what": ["Ingesta de datos — Elo de ~50 000 internacionales, cuotas de casas de apuestas y pronósticos de expertos, combinados en la fuerza de cada equipo.",
                 "El modelo — un motor Monte Carlo que juega el torneo de 48 equipos decenas de miles de veces.",
                 "Backtest y calibración — puntuación fuera de muestra (RPS) que arbitra cada cambio del modelo.",
                 "La web — este sitio (React + Vite), en seis idiomas."],
        "data_h": "Datos y licencia",
        "data": "Construido sobre fuentes abiertas y públicas. Licencia MIT. Una predicción estadística, no un pronóstico seguro, y no afiliada ni avalada por la FIFA.",
    },
    "fr": {
        "title": "Code ouvert — le modèle et ce site sont ouverts | Probaball",
        "desc": "Tout le pronostic Coupe du monde 2026 de Probaball est en open source sous licence MIT : ingestion des données, le modèle Monte Carlo, le backtest et cette application web. Voir le code sur GitHub.",
        "crumb": "Code ouvert", "h1": "Probaball est en open source",
        "lede": "Un pronostic ne vaut que par sa transparence. C'est pourquoi tout Probaball — les données, le modèle, la simulation et cette application web — est en open source sous licence MIT. Examinez-le, questionnez-le, réutilisez-le.",
        "cta": "Voir le code sur GitHub →", "what_h": "Ce que contient le dépôt",
        "what": ["Ingestion des données — Elo sur ~50 000 matchs internationaux, cotes des bookmakers et pronostics d'experts, combinés en une force par équipe.",
                 "Le modèle — un moteur Monte Carlo qui rejoue le tournoi à 48 équipes des dizaines de milliers de fois.",
                 "Backtest et calibration — un score hors échantillon (RPS) qui arbitre chaque changement du modèle.",
                 "L'application web — ce site (React + Vite), en six langues."],
        "data_h": "Données et licence",
        "data": "Construit sur des sources ouvertes et publiques. Sous licence MIT. Un pronostic statistique, pas une prédiction — et ni affilié ni approuvé par la FIFA.",
    },
    "pt": {
        "title": "Código aberto — o modelo e este site são abertos | Probaball",
        "desc": "Toda a previsão da Copa 2026 da Probaball é de código aberto sob licença MIT: ingestão de dados, o modelo Monte Carlo, o backtest e esta aplicação web. Ver o código no GitHub.",
        "crumb": "Código aberto", "h1": "A Probaball é de código aberto",
        "lede": "Uma previsão é tão confiável quanto transparente. Por isso, toda a Probaball — os dados, o modelo, a simulação e esta aplicação web — é de código aberto sob licença MIT. Examine, questione, reutilize.",
        "cta": "Ver o código no GitHub →", "what_h": "O que há no repositório",
        "what": ["Ingestão de dados — Elo de ~50 000 jogos internacionais, odds de casas de apostas e palpites de especialistas, combinados na força de cada seleção.",
                 "O modelo — um motor Monte Carlo que joga o torneio de 48 seleções dezenas de milhares de vezes.",
                 "Backtest e calibração — pontuação fora da amostra (RPS) que arbitra cada mudança do modelo.",
                 "A aplicação web — este site (React + Vite), em seis idiomas."],
        "data_h": "Dados e licença",
        "data": "Construído sobre fontes abertas e públicas. Licença MIT. Uma previsão estatística, não um palpite certo — e não afiliada nem endossada pela FIFA.",
    },
    "de": {
        "title": "Open Source — das Modell und diese Seite sind offen | Probaball",
        "desc": "Die gesamte WM-2026-Prognose von Probaball ist Open Source unter der MIT-Lizenz: Datenaufnahme, das Monte-Carlo-Modell, der Backtest und diese Web-App. Den Code auf GitHub ansehen.",
        "crumb": "Open Source", "h1": "Probaball ist Open Source",
        "lede": "Eine Prognose ist nur so vertrauenswürdig wie sie transparent ist. Deshalb ist ganz Probaball — die Daten, das Modell, die Simulation und diese Web-App — Open Source unter der MIT-Lizenz. Prüfe es, hinterfrage es, nutze es weiter.",
        "cta": "Den Code auf GitHub ansehen →", "what_h": "Was im Repo steckt",
        "what": ["Datenaufnahme — Elo aus ~50 000 Länderspielen, Buchmacherquoten und Expertentipps, zu einer Teamstärke kombiniert.",
                 "Das Modell — eine Monte-Carlo-Engine, die das Turnier mit 48 Teams zehntausendfach durchspielt.",
                 "Backtest & Kalibrierung — Out-of-Sample-Bewertung (RPS), die jede Modelländerung überprüft.",
                 "Die Web-App — diese Seite (React + Vite), in sechs Sprachen."],
        "data_h": "Daten & Lizenz",
        "data": "Auf offenen und öffentlichen Quellen aufgebaut. MIT-lizenziert. Eine statistische Prognose, keine Vorhersage — und nicht mit der FIFA verbunden oder von ihr unterstützt.",
    },
}


def code_fragment(ct, lang):
    """SSR prose for the /code/ open-source page."""
    items = "".join(f"<li>{esc(w)}</li>" for w in ct["what"])
    return "\n".join([
        '<main id="ssr-content">',
        f'<p><a href="{url_for(lang, "/")}">← Probaball</a></p>',
        f"<h1>{esc(ct['h1'])}</h1>",
        f"<p>{esc(ct['lede'])}</p>",
        f'<p><a href="{REPO_URL}" rel="noopener">{esc(ct["cta"])}</a></p>',
        f"<h2>{esc(ct['what_h'])}</h2><ul>{items}</ul>",
        f"<h2>{esc(ct['data_h'])}</h2><p>{esc(ct['data'])}</p>",
        "</main>",
    ])


def breadcrumb(lang, crumbs):
    """crumbs: list of (name, url). Returns a BreadcrumbList JSON-LD dict."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(crumbs)
        ],
    }


def website_ld(lang, canonical, title, desc, date_iso):
    """WebSite + dated WebPage JSON-LD for the home page. dateModified is the
    forecast's data date, so Google sees the page refreshing daily."""
    return {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "@id": ORIGIN + "/#website", "url": ORIGIN + "/",
             "name": "Probaball", "inLanguage": lang},
            {"@type": "WebPage", "@id": canonical + "#webpage", "url": canonical,
             "isPartOf": {"@id": ORIGIN + "/#website"}, "name": title,
             "description": desc, "inLanguage": lang, "dateModified": date_iso},
        ],
    }


def inject(template, fragment, *, title, desc, canonical, lang, route, crumb=None, ld=None):
    h = template.replace('<div id="root"></div>', f'<div id="root">{fragment}</div>')
    h = re.sub(r"<title>.*?</title>", f"<title>{esc(title)}</title>", h, count=1, flags=re.S)
    h = re.sub(r'<meta\s+name="description"[^>]*?/>',
               f'<meta name="description" content="{esc(desc)}" />', h, count=1, flags=re.S)
    h = re.sub(r'<link rel="canonical"[^>]*?/>',
               f'<link rel="canonical" href="{canonical}" />', h, count=1, flags=re.S)
    h = h.replace('<html lang="en">', f'<html lang="{lang}">', 1)
    h = re.sub(r'<meta property="og:url"[^>]*?/>',
               f'<meta property="og:url" content="{canonical}" />', h, count=1, flags=re.S)
    h = re.sub(r'<meta property="og:locale"[^>]*?/>',
               f'<meta property="og:locale" content="{OG_LOCALE[lang]}" />', h, count=1, flags=re.S)
    # Localize the social cards too: match each page's title/description, so an
    # English share doesn't show Swedish text.
    # These tags are multi-line in the built HTML, so allow whitespace between
    # <meta and the attribute (and across the content attribute).
    h = re.sub(r'<meta\s+property="og:title"[^>]*?/>',
               f'<meta property="og:title" content="{esc(title)}" />', h, count=1, flags=re.S)
    h = re.sub(r'<meta\s+property="og:description"[^>]*?/>',
               f'<meta property="og:description" content="{esc(desc)}" />', h, count=1, flags=re.S)
    h = re.sub(r'<meta\s+name="twitter:title"[^>]*?/>',
               f'<meta name="twitter:title" content="{esc(title)}" />', h, count=1, flags=re.S)
    h = re.sub(r'<meta\s+name="twitter:description"[^>]*?/>',
               f'<meta name="twitter:description" content="{esc(desc)}" />', h, count=1, flags=re.S)

    extras = []
    for l in LANGS:
        extras.append(f'<link rel="alternate" hreflang="{l}" href="{url_for(l, route)}" />')
    for hl, base_lang in REGION_ALTERNATES.items():
        extras.append(f'<link rel="alternate" hreflang="{hl}" href="{url_for(base_lang, route)}" />')
    extras.append(f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}/" />')
    for l in LANGS:
        if l != lang:
            extras.append(f'<meta property="og:locale:alternate" content="{OG_LOCALE[l]}" />')
    for block in ([crumb] if crumb else []) + (ld or []):
        extras.append('<script type="application/ld+json">'
                      + json.dumps(block, ensure_ascii=False) + "</script>")
    h = h.replace("</head>", "    " + "\n    ".join(extras) + "\n  </head>", 1)
    return h


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    api_base, index_path = sys.argv[1], sys.argv[2]
    base = os.path.dirname(index_path)
    d = fetch(api_base.rstrip("/") + "/api/canonical")
    template = open(index_path, encoding="utf-8").read()
    teams = d.get("teams", [])
    groups = d.get("groups", {})
    n, date = d.get("n", 0), d.get("date", "")
    lastmod = datetime.date.today().isoformat()
    en = {t["team"]: t.get("name_en", t["team"]) for t in teams}
    for g, rows in groups.items():
        for r in rows:
            r["team_en"] = en.get(r["team"], r["team"])

    # Group matches: (route, group, match) for the per-match prediction pages.
    gm = d.get("group_matches", {})
    match_pages = []
    for g, ms in gm.items():
        for m in ms:
            slug = slugify(en.get(m["home"], m["home"])) + "-vs-" + slugify(en.get(m["away"], m["away"]))
            match_pages.append((f"/match/{slug}/", g, m))

    # Bare routes (language-agnostic); each is emitted once per language.
    routes = ["/", "/evaluation/", "/bracket/", "/code/"] + [f"/lag/{slugify(t['name_en'])}/" for t in teams] \
             + [f"/grupp/{g.lower()}/" for g in groups] \
             + [r for (r, _, _) in match_pages]

    count = 0
    for lang in LANGS:
        tr = T[lang]
        gw = tr["group_word"]
        home_url = url_for(lang, "/")

        # Home
        write(out_path(base, lang, "/"), inject(
            template, home_fragment(tr, lang, d, teams, groups),
            title=tr["home_title"], desc=tr["home_desc"],
            canonical=home_url, lang=lang, route="/",
            ld=[website_ld(lang, home_url, tr["home_title"], tr["home_desc"], date)]))
        count += 1

        # Evaluation
        ev_route = "/evaluation/"
        ev_crumb = breadcrumb(lang, [
            (tr["crumb_home"], home_url),
            (tr["eval_crumb"], url_for(lang, ev_route)),
        ])
        write(out_path(base, lang, ev_route), inject(
            template, eval_fragment(tr, lang, d),
            title=tr["eval_title"], desc=tr["eval_desc"],
            canonical=url_for(lang, ev_route), lang=lang, route=ev_route, crumb=ev_crumb))
        count += 1

        # Bracket / knockout odds
        br_route = "/bracket/"
        br_crumb = breadcrumb(lang, [
            (tr["crumb_home"], home_url),
            (tr["bracket_crumb"], url_for(lang, br_route)),
        ])
        write(out_path(base, lang, br_route), inject(
            template, bracket_fragment(tr, lang, d, teams),
            title=tr["bracket_title"], desc=tr["bracket_desc"],
            canonical=url_for(lang, br_route), lang=lang, route=br_route, crumb=br_crumb))
        count += 1

        # Open source
        co_route = "/code/"
        ct = CODE_T[lang]
        co_crumb = breadcrumb(lang, [
            (tr["crumb_home"], home_url),
            (ct["crumb"], url_for(lang, co_route)),
        ])
        write(out_path(base, lang, co_route), inject(
            template, code_fragment(ct, lang),
            title=ct["title"], desc=ct["desc"],
            canonical=url_for(lang, co_route), lang=lang, route=co_route, crumb=co_crumb))
        count += 1

        # Teams
        for t in teams:
            slug = slugify(t["name_en"])
            route = f"/lag/{slug}/"
            name = team_name(t, lang)
            g = t["group"]
            crumb = breadcrumb(lang, [
                (tr["crumb_home"], home_url),
                (f"{gw} {g}", url_for(lang, f"/grupp/{g.lower()}/")),
                (name, url_for(lang, route)),
            ])
            write(out_path(base, lang, route), inject(
                template, team_fragment(tr, lang, t, n, date),
                title=tr["team_title"].format(name=name),
                desc=tr["team_desc"].format(name=name, champ=pct(t["champion"], lang),
                                            final=pct(t["final"], lang)),
                canonical=url_for(lang, route), lang=lang, route=route, crumb=crumb))
            count += 1

        # Groups
        for g, rows in groups.items():
            route = f"/grupp/{g.lower()}/"
            crumb = breadcrumb(lang, [
                (tr["crumb_home"], home_url),
                (f"{gw} {g}", url_for(lang, route)),
            ])
            write(out_path(base, lang, route), inject(
                template, group_fragment(tr, lang, g, rows, date),
                title=tr["group_title"].format(g=g),
                desc=tr["group_desc"].format(g=g),
                canonical=url_for(lang, route), lang=lang, route=route, crumb=crumb))
            count += 1

        # Match prediction pages ([A] vs [B])
        for route, g, m in match_pages:
            v = match_vars(tr, lang, m, g, en)
            crumb = breadcrumb(lang, [
                (tr["crumb_home"], home_url),
                (f"{gw} {g}", url_for(lang, f"/grupp/{g.lower()}/")),
                (f'{v["home"]} – {v["away"]}', url_for(lang, route)),
            ])
            write(out_path(base, lang, route), inject(
                template, match_fragment(tr, lang, m, g, en),
                title=tr["match_title"].format(**v),
                desc=tr["match_desc"].format(**v),
                canonical=url_for(lang, route), lang=lang, route=route, crumb=crumb,
                ld=[faq_ld(match_faq_pairs(tr, v))]))
            count += 1

    # Sitemaps. We publish a sitemap INDEX (sitemap.xml) pointing at one child
    # sitemap per language (sitemap-<lang>.xml, ~one per route). GSC fetches an
    # index of smaller files more reliably than one large urlset, and each <url>
    # still carries the full hreflang set (Google reads hreflang across the whole
    # index, so reciprocity holds). robots.txt points at the index; children are
    # discovered through it.
    by_lang = {l: [] for l in LANGS}
    for route in routes:
        alts = "".join(
            f'<xhtml:link rel="alternate" hreflang="{l}" href="{url_for(l, route)}"/>'
            for l in LANGS
        ) + "".join(
            f'<xhtml:link rel="alternate" hreflang="{hl}" href="{url_for(base_lang, route)}"/>'
            for hl, base_lang in REGION_ALTERNATES.items()
        ) + f'<xhtml:link rel="alternate" hreflang="x-default" href="{ORIGIN}/"/>'
        for l in LANGS:
            loc = url_for(l, route)
            prio = "1.0" if route == "/" and l == ROOT_LANG else ("0.8" if route == "/" else "0.6")
            by_lang[l].append(
                f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>"
                f"<changefreq>weekly</changefreq><priority>{prio}</priority>{alts}</url>"
            )
    child_names = [f"sitemap-{l}.xml" for l in LANGS]
    for l, name in zip(LANGS, child_names):
        write(os.path.join(base, name),
              '<?xml version="1.0" encoding="UTF-8"?>\n'
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
              'xmlns:xhtml="http://www.w3.org/1999/xhtml">'
              + "".join(by_lang[l]) + "</urlset>\n")
    write(os.path.join(base, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<sitemap><loc>{ORIGIN}/{n}</loc><lastmod>{lastmod}</lastmod></sitemap>"
                    for n in child_names)
          + "</sitemapindex>\n")

    print(f"prerendered {count} pages across {len(LANGS)} languages "
          f"({len(routes)} routes) + sitemap index ({len(child_names)} child sitemaps) into {base}")


if __name__ == "__main__":
    main()
