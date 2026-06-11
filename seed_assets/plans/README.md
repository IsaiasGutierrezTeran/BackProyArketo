# Planos de ejemplo para el seeder

Deja aquí imágenes de planos reales (`.png`, `.jpg`, `.jpeg`) y corre:

    python manage.py seed_example_plans

El comando creará un proyecto "Planos de ejemplo" con un plano por cada imagen
encontrada y generará su modelo 3D (detector `mock` por defecto; usa el real
levantando `floorplan-api` + `DETECTION_DEFAULT_DETECTOR=maskrcnn`).

Si esta carpeta está vacía, el seeder **genera 3 planos sintéticos realistas**
(multi-habitación con áreas y garaje) para que tengas datos de demostración.
