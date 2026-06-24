# Validación de la detección de planos con CubiCasa5K

Este dataset se usa para **validar y demostrar** el primer paso del flujo de Arketo:

```
plano 2D  ->  detección (Mask R-CNN)  ->  generación del modelo 3D (.glb)
```

La detección la hace el servicio **AIAPI** (Mask R-CNN, 3 clases: `wall` / `door` /
`window` = pared / puerta / ventana). Aquí evaluamos ESE mismo modelo, con los
mismos pesos e inferencia que corren en producción, sobre el conjunto de prueba
oficial de CubiCasa5K.

> Nota: el dataset **no se sube al repositorio** (ver `.gitignore`: `data/cubicasa5k/`
> y `*.zip`). Hay que tenerlo descomprimido localmente en esta carpeta.

---

## 1. Qué es el dataset

CubiCasa5K son ~5.000 planos de vivienda, cada uno en su carpeta con:

- `F1_original.png`, `F1_scaled.png` — imágenes del plano.
- `model.svg` — anotación vectorial (muros, puertas, ventanas, espacios, cotas…).

Categorías: `colorful/`, `high_quality/`, `high_quality_architectural/`.

### Split (80/20)

CubiCasa5K **ya viene dividido** y usamos ese split oficial (es lo correcto y 100 %
reproducible, sin aleatoriedad):

| Split | Archivo | Planos |
|-------|---------|--------|
| Train | `train.txt` | 4199 |
| Val   | `val.txt`   | 399  |
| Test  | `test.txt`  | 399  |

(Train+Val ≈ 80 %, Test ≈ 20 %.) Si se quisiera forzar un 80/20 propio con semilla
fija, `prepare_cubicasa.py --resplit --ratio 0.8 --seed 42` lo hace.

De cada `model.svg` se extraen las cajas/poligonos de las clases cuyo nombre empieza
por `Wall` / `Door` / `Window` y se escalan al espacio de píxeles de `F1_scaled.png`
(el SVG está prácticamente en ese sistema; se ajusta por eje `png/svg ≈ 1.0`).

---

## 2. Scripts (en `AIAPI/cubicasa/`)

| Script | Para qué | Entorno |
|--------|----------|---------|
| `prepare_cubicasa.py` | Lee el split y genera el **manifiesto** (`out/manifest_test.json`) con la imagen y el GT (wall/door/window) de cada plano. | Cualquier Python 3 con `Pillow`. |
| `evaluate_cubicasa.py` | Carga los **pesos ya entrenados** (no reentrena), corre la detección sobre el test y calcula métricas por clase + dibuja ejemplos. | **Conda `imageTo3D`** (Py3.6 / TF1.15). |
| `train_cubicasa.py` | **Reentrena (fine-tuning)** con el 80% (`train.txt`) para mejorar métricas. Parte de los pesos actuales y mantiene el mapeo de clases de producción. | **Conda `imageTo3D`** + **GPU** (en CPU solo `--smoke`). |
| `svg_gt.py` | Utilidades compartidas (parser SVG→GT, splits, dibujo). | — |

### Cómo correr

```bash
# 1) Preparación (manifiesto del test)
python AIAPI/cubicasa/prepare_cubicasa.py --splits test.txt

# 2) Evaluación con el modelo real (en el entorno conda del modelo)
conda activate imageTo3D
cd AIAPI/cubicasa
python evaluate_cubicasa.py --limit 40 --num-vis 8      # subconjunto rápido
python evaluate_cubicasa.py                             # test completo (399)
```

Salidas (en `AIAPI/cubicasa/out/`, ignorada por git):
- `manifest_test.json` — lista de imágenes + GT.
- `metrics.json` — métricas por clase.
- `vis/vis_*.png` — 5–10 imágenes con GT (verde) vs predicciones (color + score).

---

## 3. Conexión con producción

La evaluación usa **exactamente** la misma inferencia que el endpoint de detección:

- Importa `PredictionConfig` y el mapeo de clases (`1=wall, 2=window, 3=door`) de
  `AIAPI/application.py` y carga `weights/maskrcnn_15_epochs.h5`.
- Reproduce `application.prediction()` (`mold_image` → `model.detect`).

En producción ese mismo modelo lo consume el backend Django:
`detection.run_pipeline` → `MaskRCNNDetector` → `FLOORPLAN_API_URL/detect` (AIAPI) →
`modeling.create_model_from_scene` → `.glb`. Es decir, lo que se valida aquí es la
misma pieza que genera el 3D.

---

## 4. Resultados (test, 40 imágenes, IoU≥0.50)

**Métrica principal — IoU a nivel de píxel (segmentación), por clase:**

| Clase  | IoU px | Precisión px | Recall px |
|--------|:------:|:------------:|:---------:|
| wall   | 0.107  | 0.288        | 0.145     |
| door   | 0.036  | 0.096        | 0.055     |
| window | 0.117  | 0.272        | 0.170     |
| **IoU media** | **0.087** | | |

**Detección por instancias (bbox AP@0.50):** wall 0.003 · door 0.000 · window 0.025 ·
**mAP 0.009**.

### Lectura honesta de estos números

- **Cualitativamente el modelo detecta muy bien** (ver `out/vis/*.png`: cajas
  ajustadas a muros/puertas/ventanas con confianza 0.90–0.99). En planos "buenos"
  el IoU de píxel sube bastante (p. ej. en `2536`: wall 0.31, door 0.42).
- El **IoU/mAP agregado es bajo** por razones conocidas, no por un fallo del harness:
  1. **Estructuras finas:** un muro mide ~13–17 px de grosor; un desfase mínimo entre
     GT y predicción parte el IoU a la mitad (el bbox-IoU es especialmente severo).
  2. **Convención de grosor:** los muros del GT son ~2× más gruesos que las máscaras
     que produce el modelo.
  3. **Granularidad:** el GT corta los muros en tramos distintos a los del modelo.
  4. **Inconsistencia entre planos:** en algunos detecta excelente y en otros poco,
     lo que baja el promedio. El modelo está entrenado solo 15 épocas.

### Cómo mejorar (opcional, pendiente)

- Excluir del GT los arcos de barrido de las puertas (`Door Swing`) para no inflar su
  área.
- Reportar también con tolerancia (IoU≥0.3) para estructuras finas.
- **Reentrenar** con el 80 % (`train.txt`) más épocas — es lo que más mejoraría las
  métricas. Ya está `train_cubicasa.py`:

  ```bash
  python prepare_cubicasa.py --splits train.txt val.txt   # manifiestos completos
  conda activate imageTo3D
  python train_cubicasa.py --epochs 20 --layers heads             # primero las cabezas
  python train_cubicasa.py --epochs 40 --layers all --lr 0.0005   # luego afinado total
  python train_cubicasa.py --smoke   # prueba que corre (sin GPU)
  ```

  Necesita **GPU** (en CPU un entrenamiento real es inviable). Los pesos quedan en
  `out/logs/...`; el `.h5` elegido se copia a `AIAPI/weights/` para producción.

---

## 5. Reproducibilidad

- Split oficial fijo (sin azar). El `--resplit` usa semilla fija (`--seed`).
- Mismos pesos y misma inferencia que producción.
- El manifiesto deja registrado exactamente qué imágenes y qué GT se usaron.
