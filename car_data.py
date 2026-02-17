# car_data.py

CAR_BRANDS = [
    "Toyota", "BMW", "Mercedes-Benz", "Audi", "Volkswagen",
    "Lada", "Kia", "Hyundai", "Renault", "Nissan",
    "Ford", "Chevrolet", "Mazda", "Skoda", "Mitsubishi"
]

CAR_MODELS = {
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
    "Mitsubishi": ["Outlander", "Pajero", "L200", "ASX", "Lancer"]
}

def get_models_for_brand(brand: str) -> list:
    return CAR_MODELS.get(brand, [])
