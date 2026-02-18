# NX CAD Dataset Generator (PRT → OBJ → PNG)

Windows-лаунчер для пакетной подготовки датасета изображений деталей из Siemens NX:

**PRT → (NX Journal) → OBJ → (Python renderer) → 8 PNG (Front/Back/Right/Left/Top/Bottom/Isometric/Trimetric)**

Проект сделан для быстрого получения «CAD-скриншотов» без ручного открытия каждой детали в NX.

## Быстрый старт (для пользователей)

1. Скачать релиз (zip) и распаковать
2. Запустить `NxPipelineLauncher.exe`
3. Выбрать:
   - **PRT folder** — папка с `.prt` (можно с подпапками)
   - **PNG output folder** — куда сохранять изображения
   - **NXBIN folder** — где находится `run_journal.exe`  
     (часто автозаполняется из `UGII_BASE_DIR`)
4. Нажать **Запустить**
5. Следить за логом в окне

Логи также сохраняются в:
- `export_log.txt`
- `render_log.txt`

---

## Что входит

- **WinForms launcher (C# / .NET)**  
  Выбираешь папку с PRT и папку для PNG → жмёшь *Запустить* → получаешь OBJ и PNG + логи.

- **NX Journal (Python, NXOpen)**:  
  `export_prt_to_obj_batch.py`  
  Пакетно экспортирует `.prt` → `.obj` **без UI** (через `run_journal.exe`).

- **Python renderer**:  
  `render_folder.py`  
  Рендерит `.obj` в PNG **ортографической камерой** (похожее на NX)
  - 8 видов (включая Isometric/Trimetric)
  - авто “fit-to-view” под каждый вид (деталь не выходит за кадр)
  - сохранение структуры подпапок
  - логирование
  - пропуск уже существующих PNG (если не включён `--overwrite`)
  - опциональный режим `--edges` (экспериментально; отображает рёбра триангуляции)

---

## Требования

- **Windows 10/11**
- **Siemens NX установлен**

## Среда тестировки

Проект протестирован в следующей конфигурации:

- Siemens NX 1899
- NXOpen Python API (journal execution via run_journal.exe)
- Embedded Python 3.11.9
- Windows 10 Pro x64

Работа на других версиях NX возможна, но не гарантируется.

---

## OBJ Cache

По умолчанию OBJ-кэш создаётся автоматически:
```
<PNG output folder>/_obj_cache
```
При необходимости расположение кэша можно изменить в настройках лаунчера.

---

## Выходная структура

### OBJ-кэш (пример)

```

_obj_cache/
CategoryA/
0.0.0.0.obj
CategoryB/
1.2.3.4.obj

```

### PNG-выход (с сохранением подпапок)

```

PNG/
CategoryA/
0.0.0.0/
0.0.0.0_Front.png
0.0.0.0_Back.png
...
CategoryB/
1.2.3.4/
1.2.3.4_Front.png
...

````

---

## CLI режим (для отладки без лаунчера)

### 1) Экспорт PRT → OBJ (через NX)

Параметры передаются через переменные окружения:

- `PRT_DIR` — папка с `.prt`
- `OBJ_DIR` — папка для `.obj`
- `LOG_FILE` — путь к `export_log.txt`

Пример (PowerShell):

```powershell
$env:PRT_DIR="D:\Parts\PRT"
$env:OBJ_DIR="D:\Parts\_obj_cache"
$env:LOG_FILE="D:\Parts\export_log.txt"

"D:\Program Files\Siemens\NX1899\NXBIN\run_journal.exe" "scripts\NX\export_prt_to_obj_batch.py"
````

---

### 2) Рендер OBJ → PNG

```powershell
python scripts\Render\render_folder.py --input "D:\Parts\_obj_cache" --output "D:\Parts\PNG" --log "D:\Parts\render_log.txt"
```

Опции:

* `--overwrite` — перезаписывать PNG
* `--views "Front,Back,Right,Left,Top,Bottom,Isometric,Trimetric"`
* `--w 1280 --h 720`
* `--margin 1.2`
* `--bg 0.95`
* `--edges` — экспериментально

---

## Примечания по качеству изображения

* Используется **ортографическая камера** (как в CAD)
* Реализован авто “fit-to-view” под каждый вид
* В изометрии отверстия могут иметь слабый контраст из-за одинакового материала и освещения

---

## Сборка (для разработчиков)

1. Открыть решение в Visual Studio
2. Target: **.NET 10 / WinForms**
3. Собрать проект

Выходной exe:

```
bin/Debug/net10.0-windows/
или
bin/Release/net10.0-windows/
```

Рядом с exe положить:

```
Tools/py311/  (если используется Embedded Python)
```
