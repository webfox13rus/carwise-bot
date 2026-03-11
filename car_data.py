# Список популярных марок автомобилей (можно расширить)
BRANDS = [
    "Lada", "Toyota", "Kia", "Hyundai", "Renault", "Volkswagen", "Skoda", "Ford",
    "Nissan", "BMW", "Mercedes-Benz", "Audi", "Mazda", "Mitsubishi", "Subaru",
    "Honda", "Suzuki", "Opel", "Peugeot", "Citroen", "Fiat", "Volvo", "Land Rover",
    "Jeep", "Chery", "Geely", "Haval", "Exeed", "Changan", "Great Wall", "BYD",
    "Lifan", "Zotye", "Datsun", "Ravon", "Chevrolet", "Daihatsu", "Alfa Romeo",
    "Porsche", "Jaguar", "Lexus", "Infiniti", "Acura", "Cadillac", "Chrysler",
    "Dodge", "Mini", "Smart", "Tesla", "Genesis", "Reno", "Москвич", "ГАЗ", "УАЗ"
]

# Словарь моделей для каждой марки (пример, можно дополнить)
MODELS_BY_BRAND = {
    "Lada": ["Granta", "Vesta", "XRAY", "Largus", "Niva", "4x4", "Kalina", "Priora"],
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Prado", "Highlander", "C-HR", "Yaris"],
    "Kia": ["Rio", "Sportage", "Sorento", "Optima", "Ceed", "Picanto", "Stinger", "K5"],
    "Hyundai": ["Solaris", "Creta", "Tucson", "Elantra", "Santa Fe", "Palisade", "Sonata", "ix35"],
    "Renault": ["Logan", "Sandero", "Duster", "Kaptur", "Arkana", "Koleos", "Megan"],
    "Volkswagen": ["Polo", "Jetta", "Tiguan", "Passat", "Golf", "Tuareg", "Teramont"],
    "Skoda": ["Rapid", "Octavia", "Kodiaq", "Karoq", "Superb", "Fabia"],
    "Ford": ["Focus", "Mondeo", "Kuga", "EcoSport", "Explorer", "Fusion", "Mustang"],
    "Nissan": ["Qashqai", "X-Trail", "Terrano", "Juke", "Murano", "Patrol", "Almera"],
    "BMW": ["3 series", "5 series", "X3", "X5", "X1", "X6", "1 series", "7 series"],
    "Mercedes-Benz": ["E-Class", "C-Class", "S-Class", "GLE", "GLC", "GLA", "GLB", "G-Class"],
    "Audi": ["A3", "A4", "A6", "Q3", "Q5", "Q7", "TT"],
    "Mazda": ["3", "6", "CX-5", "CX-9", "MX-5", "CX-30"],
    "Mitsubishi": ["Outlander", "Pajero", "L200", "ASX", "Lancer"],
    "Subaru": ["Forester", "Outback", "Impreza", "XV", "Legacy"],
    "Honda": ["CR-V", "Civic", "Accord", "Pilot", "HR-V"],
    "Chery": ["Tiggo 4", "Tiggo 7", "Tiggo 8", "Arrizo 5", "Arrizo 8"],
    "Geely": ["Coolray", "Atlas", "Tugella", "Emgrand", "Monjaro"],
    "Haval": ["Jolion", "F7", "F7x", "H9", "Dargo"],
    "Exeed": ["LX", "TXL", "VX"],
    "Changan": ["CS35", "CS55", "CS75", "UNI-K", "Alsvin"],
    "BYD": ["Song", "Tang", "Han", "Yuan", "Seal"],
    "ГАЗ": ["3110", "31105", "3302", "2705", "Соболь"],
    "УАЗ": ["Патриот", "Хантер", "Буханка", "Пикап"],
    "Москвич": ["3", "6", "2141"],
    "Tesla": ["Model 3", "Model Y", "Model S", "Model X", "Cybertruck"],
}

# Для удобства можно добавить функцию получения моделей с обработкой отсутствия
def get_models(brand):
    return MODELS_BY_BRAND.get(brand, [])
