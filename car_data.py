# car_data.py

# Все марки (старые + новые китайские)
CAR_BRANDS = [
    # Европейские/японские/корейские (были ранее)
    "Toyota", "BMW", "Mercedes-Benz", "Audi", "Volkswagen",
    "Lada", "Kia", "Hyundai", "Renault", "Nissan",
    "Ford", "Chevrolet", "Mazda", "Skoda", "Mitsubishi",
    # Китайские бренды (новые)
    "Chery", "Geely", "Haval", "Changan", "Exeed",
    "OMODA", "Jaecoo", "Great Wall", "Tank", "GAC",
    "FAW", "BAIC", "Dongfeng", "Jetour", "Livan",
    "Voyah", "SWM", "Kaiyi", "Ora", "Wey"
]

# Модели по маркам
CAR_MODELS = {
    # Существующие модели (оставляем без изменений)
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Yaris"],
    "BMW": ["X5", "X3", "3 Series", "5 Series", "M5"],
    "Mercedes-Benz": ["E-Class", "S-Class", "GLC", "GLE", "A-Class"],
    "Audi": ["A4", "A6", "Q5", "Q7", "TT"],
    "Volkswagen": ["Golf", "Passat", "Tiguan", "Polo", "Jetta"],
    "Lada": ["Vesta", "Granta", "Niva", "Largus", "XRAY"],
    "Kia": ["Rio", "Sportage", "Sorento", "Ceed", "Optima"],
    "Hyundai": ["Solaris", "Creta", "Tucson", "Elantra", "Santa Fe"],
    "Renault": ["Logan", "Duster", "Sandero", "Kaptur", "Arkana"],
    "Nissan": ["Qashqai", "X-Trail", "Juke", "Almera", "Terrano"],
    "Ford": ["Focus", "Mondeo", "Kuga", "EcoSport", "Fiesta"],
    "Chevrolet": ["Cruze", "Lacetti", "Niva", "Aveo", "Spark"],
    "Mazda": ["CX-5", "CX-9", "Mazda3", "Mazda6", "MX-5"],
    "Skoda": ["Octavia", "Rapid", "Kodiaq", "Karoq", "Superb"],
    "Mitsubishi": ["Outlander", "Pajero", "L200", "ASX", "Lancer"],
    
    # Китайские модели
    "Chery": ["Tiggo 4", "Tiggo 7", "Tiggo 8", "Tiggo 8 Pro", "Arrizo 8"],
    "Geely": ["Coolray", "Atlas", "Monjaro", "Emgrand", "Tugella"],
    "Haval": ["Jolion", "F7", "F7x", "Dargo", "H9"],
    "Changan": ["CS35", "CS55", "CS75", "Uni-K", "Uni-T", "Alsvin"],
    "Exeed": ["LX", "TXL", "VX", "RX"],
    "OMODA": ["C5"],
    "Jaecoo": ["J7"],
    "Great Wall": ["Wingle 7", "Poer"],
    "Tank": ["300", "500", "700"],
    "GAC": ["GS3", "GS8", "GN8"],
    "FAW": ["Bestune T77", "Bestune T99"],
    "BAIC": ["X35", "X55", "U5 Plus"],
    "Dongfeng": ["580", "580 Pro", "Aeolus"],
    "Jetour": ["X70", "X90", "Dashing"],
    "Livan": ["X3 Pro"],
    "Voyah": ["Free", "Dream"],
    "SWM": ["G01", "G05"],
    "Kaiyi": ["X3", "X7"],
    "Ora": ["03 (Good Cat)"],
    "Wey": ["Coffee 01", "Coffee 02"]
}

def get_models_for_brand(brand: str) -> list:
    """Возвращает список моделей для марки или пустой список, если марка не найдена"""
    return CAR_MODELS.get(brand, [])
