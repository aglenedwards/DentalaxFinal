"""
Zentrale Preiskonfiguration für Dentalax.
Alle Preisangaben sind Nettopreise in EUR.
Stripe-Beträge sind in Cent (mal 100).

NUR DIESE DATEI muss bei einer Preisänderung angepasst werden.
"""

PAKET_PREISE = {
    'basis': {
        'monatlich': 0,
        'jaehrlich': 0,
    },
    'premium': {
        'monatlich': 79,       # EUR netto / Monat
        'jaehrlich': 829,      # EUR netto / Jahr (ca. 12.5% günstiger als 12× monatlich)
        'original_monatlich': 99,
        'original_jaehrlich': 1189,
        'rabatt_monatlich': 20,   # % Ersparnis ggü. Originalpreis
        'rabatt_jaehrlich': 30,
        'aequivalent_monatlich': 69,   # 829 / 12 gerundet
    },
    'premiumplus': {
        'monatlich': 99,       # EUR netto / Monat
        'jaehrlich': 999,      # EUR netto / Jahr (ca. 16% günstiger als 12× monatlich)
        'original_monatlich': 119,
        'original_jaehrlich': 1428,
        'rabatt_monatlich': 20,
        'rabatt_jaehrlich': 30,
        'aequivalent_monatlich': 83,   # 999 / 12 gerundet
    },
}

# Stripe-Beträge in Cent (für Rechnungsdarstellung / Fallback)
STRIPE_PREISE_CENT = {
    'premium': {
        'monatlich': 7900,
        'jaehrlich': 82900,
    },
    'premiumplus': {
        'monatlich': 9900,
        'jaehrlich': 99900,
    },
}

# Stripe Price IDs – aus dem Stripe-Dashboard
# Beim Wechsel der Preise: neue Price IDs in Stripe anlegen und hier eintragen.
STRIPE_PRICE_IDS = {
    'premium': {
        'monatlich': 'price_1TKHCvDNQHMKEm2lOhY3gSD9',  # TEST - original: price_1TKEybDNQHMKEm2lhCloD2dF
        'jaehrlich': 'price_1TKF0LDNQHMKEm2l9hpxkTvj',
    },
    'premiumplus': {
        'monatlich': 'price_1TKF1qDNQHMKEm2lwJqZva8x',
        'jaehrlich': 'price_1TKF3DDNQHMKEm2lfQpUB9nd',
    },
}
