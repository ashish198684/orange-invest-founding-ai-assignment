"""Small deterministic language adapter for G2. General language evaluation is G4."""
from datetime import datetime, timedelta
import re

class ScriptedModel:
    def interpret(self, text, now):
        lower = text.lower()
        patch = {}
        for service in ('plumber', 'electrician', 'ac servicing'):
            if service in lower:
                patch['service'] = service
        for area in ('Indiranagar', 'Koramangala'):
            if area.lower() in lower:
                patch['area'] = area
        budget = re.search(r'(?:under|budget|up to)\s*(?:₹|rs\.?\s*)?([\d,]+)', lower)
        if budget:
            patch['budget_inr'] = int(budget[1].replace(',', ''))
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if 'this week' in lower:
            end = start + timedelta(days=7-start.weekday())
            patch['date_window'] = {'start': start.isoformat(), 'end': end.isoformat()}
        elif 'saturday' in lower:
            start += timedelta(days=(5-start.weekday()) % 7)
            patch['date_window'] = {'start': start.isoformat(), 'end': (start+timedelta(days=1)).isoformat()}
        elif 'tomorrow' in lower:
            start += timedelta(days=1)
            patch['date_window'] = {'start': start.isoformat(), 'end': (start+timedelta(days=1)).isoformat()}
        prefs = {}
        if 'mornings' in lower:
            prefs['latest_hour'] = 12
        earliest = re.search(r'(?:not before|after)\s*(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)?', lower)
        if earliest:
            hour = int(earliest[1])
            if earliest[2] and earliest[2].startswith('p') and hour < 12:
                hour += 12
            prefs['earliest_hour'] = hour
        if prefs:
            patch['preferences'] = prefs
        return patch
