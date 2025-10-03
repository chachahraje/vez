# Tento skript je bot pro hru, kde stavíte věž z kostek.
# Bot dynamicky měří rychlost pohybující se kostky a na základě toho
# přesně předvídá, kdy stisknout mezerník pro umístění kostky.

# --- Potřebné knihovny ---
# Ujistěte se, že máte nainstalované všechny potřebné knihovny.
# Otevřete terminál (příkazový řádek) a spusťte:
# pip install numpy opencv-python pyautogui keyboard mss

import time
import keyboard
import numpy as np
import cv2
import mss
import pyautogui

# ==============================================================================
# --- NASTAVENÍ BOTA ---
# Tuto část musíte upravit podle vaší hry a obrazovky.
# ==============================================================================

# 1. OBLAST HRY (GAME_REGION)
#    Toto je nejdůležitější nastavení. Musíte botovi říct, kde na obrazovce
#    se hra nachází. Je to obdélník definovaný:
#    - 'left': počet pixelů od levého okraje obrazovky
#    - 'top': počet pixelů od horního okraje obrazovky
#    - 'width': šířka herní oblasti v pixelech
#    - 'height': výška herní oblasti v pixelech
#
#    JAK ZJISTIT HODNOTY?
#    Spusťte si Python v terminálu a napište:
#    >>> import pyautogui
#    >>> pyautogui.displayMousePosition()
#    Poté hýbejte myší a terminál vám bude ukazovat její souřadnice (X, Y).
#    - Najeďte myší na LEVÝ HORNÍ roh herní plochy a zapište si X a Y.
#      To jsou vaše hodnoty 'left' a 'top'.
#    - Najeďte myší na PRAVÝ DOLNÍ roh a zapište si X a Y.
#    - 'width' = (pravý dolní X) - (levý horní X)
#    - 'height' = (pravý dolní Y) - (levý horní Y)
#
#    Zadejte úroveň, na které má bot začít (číslo od 1 do 15).
STARTING_LEVEL = 1

def calculate_game_region(level: int) -> dict:
    """
    Vrátí souřadnice herní oblasti na základě zvolené úrovně.
    Používá vyhledávací tabulku s přesnými hodnotami 'top' pro každou úroveň.
    """
    # Vyhledávací tabulka pro 'top' souřadnici na základě dat od uživatele
    LEVEL_TOPS = {
        1: 810, 2: 747, 3: 689, 4: 628, 5: 569, 6: 518,
        7: 791, 8: 729, 9: 669, 10: 611, 11: 552, 12: 491,
        13: 432, 14: 374, 15: 312,
    }

    if level not in LEVEL_TOPS:
        print(f"Chyba: Neplatná úroveň {level}. Zvolte úroveň od 1 do 15.")
        # V případě neplatného vstupu použijeme jako zálohu úroveň 1
        print("Používám výchozí úroveň 1.")
        level = 1

    # Základní hodnoty, které se nemění
    BASE_LEFT = 660
    BASE_WIDTH = 603
    BASE_HEIGHT = 64

    return {
        'left': BASE_LEFT,
        'top': LEVEL_TOPS[level],
        'width': BASE_WIDTH,
        'height': BASE_HEIGHT
    }

# Herní oblast (GAME_REGION) se nyní počítá až uvnitř funkce main(),
# aby se zajistilo, že se použijí správné hodnoty pro zvolenou úroveň.

# 1.1 OKNO PRO LADĚNÍ (DEBUG WINDOW)
#     Pokud nastavíte na True, bot zobrazí okno, ve kterém v reálném čase
#     uvidíte, co snímá, a kde detekoval kostku. Užitečné pro ladění.
SHOW_DEBUG_WINDOW = True


# 2. BARVY KOSTEK
#    Definice barev pro různé úrovně.
YELLOW_BLOCK_COLOR_RGB = (236, 168, 44)  # Pro úrovně 6-15
BLUE_BLOCK_COLOR_RGB = (45, 170, 232)    # Pro úrovně 1-5

# Výběr barvy a dalších parametrů se nyní provádí dynamicky uvnitř funkce main().

# 3. HERNÍ PARAMETRY
#    Počet sloupců, mezi kterými kostka přeskakuje.
NUM_COLUMNS = 10

# --- NASTAVENÍ PRO NÍZKÉ ÚROVNĚ (1-5) ---
# Používá se pro modré kostky a více bloků.
LOW_LEVEL_CONFIG = {
    "COLOR_TOLERANCE": 45,
    "TARGET_COLUMN": 9,
    "TRIGGER_COLUMN_OFFSET": 1,
    "INPUT_BURST_COUNT": 3,
    "INPUT_BURST_DELAY_MS": 7,
    "DETECTION_LATENCY_MS": 15
}

# --- NASTAVENÍ PRO VYSOKÉ ÚROVNĚ (6-15) ---
# Používá se pro žluté kostky a jeden blok. Upravte podle potřeby.
HIGH_LEVEL_CONFIG = {
    "COLOR_TOLERANCE": 25,
    "TARGET_COLUMN": 8,
    "TRIGGER_COLUMN_OFFSET": 2,
    "INPUT_BURST_COUNT": 3,
    "INPUT_BURST_DELAY_MS": 7,
    "DETECTION_LATENCY_MS": 15
}


# ==============================================================================
# --- KÓD BOTA ---
# Od této části byste neměli nic měnit, pokud nevíte, co děláte.
# ==============================================================================

# Hodnoty jako BLOCK_COLOR_BGR a COLUMN_WIDTH se nyní počítají v main().

def find_block_edges(sct_instance, level: int, game_region: dict, block_color_bgr: np.ndarray, color_tolerance: int):
    """
    Snímá herní obrazovku a najde kraje/střed kostek.
    - Pro úrovně 1-4: Vrací posunuté kraje ohraničujícího obdélníku všech kostek.
    - Pro úrovně 5+: Vrací střed největší kostky (jako left_x i right_x).
    Vrací: (left_x, right_x, debug_frame)
    """
    try:
        img = sct_instance.grab(game_region)
        img_np = np.array(img)
        frame = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
        debug_frame = frame.copy() if SHOW_DEBUG_WINDOW else None

        lower_bound = np.maximum(0, block_color_bgr - color_tolerance)
        upper_bound = np.minimum(255, block_color_bgr + color_tolerance)
        mask = cv2.inRange(frame, lower_bound, upper_bound)

        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, None, debug_frame

        significant_contours = [c for c in contours if cv2.contourArea(c) > 50]
        if not significant_contours:
            return None, None, debug_frame

        left_x, right_x, center_y = 0, 0, 0

        # Pro úrovně 1-4: Logika dvou posunutých bodů
        if 1 <= level <= 4:
            all_points = np.vstack([c for c in significant_contours])
            x, y, w, h = cv2.boundingRect(all_points)
            left_x, right_x = x + 30, x + w - 30
            if left_x >= right_x: # Pojistka pro úzké bloky
                left_x, right_x = x, x + w
            center_y = y + h // 2
            if SHOW_DEBUG_WINDOW:
                cv2.drawContours(debug_frame, significant_contours, -1, (0, 255, 0), 2)
                cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                cv2.circle(debug_frame, (left_x, center_y), 5, (0, 0, 255), -1) # Levý bod
                cv2.circle(debug_frame, (right_x, center_y), 5, (255, 0, 0), -1) # Pravý bod
        # Pro úrovně 5+: Logika jednoho středového bodu
        else:
            largest_contour = max(significant_contours, key=cv2.contourArea)
            M = cv2.moments(largest_contour)
            if M["m00"] == 0:
                return None, None, debug_frame
            center_x = int(M["m10"] / M["m00"])
            center_y = int(M["m01"] / M["m00"])
            left_x = right_x = center_x # Vracíme střed jako oba body
            if SHOW_DEBUG_WINDOW:
                cv2.drawContours(debug_frame, [largest_contour], -1, (0, 255, 0), 2)
                cv2.circle(debug_frame, (center_x, center_y), 5, (0, 0, 255), -1) # Jen jeden bod

        if SHOW_DEBUG_WINDOW:
            for i in range(1, NUM_COLUMNS):
                line_x = int(i * (game_region['width'] / NUM_COLUMNS))
                cv2.line(debug_frame, (line_x, 0), (line_x, game_region['height']), (255, 255, 0), 1)

        return left_x, right_x, debug_frame

    except Exception as e:
        print(f"Vyskytla se chyba při zpracování obrazu: {e}")
        return None, None, None

def calculate_stable_dwell_time(samples, max_samples=30):
    """
    Z nejnovějších vzorků vypočítá stabilní průměrný čas na sloupec.
    - Omezuje historii na `max_samples`.
    - Filtruje odlehlé hodnoty, aby byl výpočet robustní.
    """
    if len(samples) > max_samples:
        samples = samples[-max_samples:]

    if not samples:
        return None, samples

    # Vyloučíme extrémní hodnoty (např. při změně směru)
    stable_samples = [s for s in samples if 0.01 < s < 0.25]
    if not stable_samples:
        return None, samples

    return np.mean(stable_samples), samples

def main():
    """
    Hlavní smyčka bota s kontinuálním měřením a dvoufázovou synchronizací.
    """
    # --- Lokální proměnné pro správu hry ---
    current_level = STARTING_LEVEL

    # --- Dynamické načtení konfigurace ---
    if 1 <= current_level <= 5:
        config = LOW_LEVEL_CONFIG
        block_color_rgb = BLUE_BLOCK_COLOR_RGB
    else:
        config = HIGH_LEVEL_CONFIG
        block_color_rgb = YELLOW_BLOCK_COLOR_RGB

    game_region = calculate_game_region(current_level)
    block_color_bgr = np.array(block_color_rgb[::-1])
    column_width = game_region['width'] / NUM_COLUMNS

    print("="*50)
    print(f"Start na úrovni: {current_level}, Cílová oblast: {game_region}")
    print(f"Použitá konfigurace: {config}")
    print("Bot se spouští za 3 sekundy...")
    print("PŘEPNĚTE SE DO OKNA SE HROU!")
    print("Pro ukončení bota stiskněte a držte klávesu 'q'.")
    print("="*50)
    time.sleep(3)

    # --- Stavové proměnné bota ---
    state = 'SYNC_WAIT_RIGHT'
    last_pos_info = {'left': -1, 'time': 0}
    direction = 1
    dwell_time_samples = []

    with mss.mss() as sct:
        while not keyboard.is_pressed('q'):
            left_x, right_x, debug_frame = find_block_edges(sct, current_level, game_region, block_color_bgr, config["COLOR_TOLERANCE"])

            if SHOW_DEBUG_WINDOW and debug_frame is not None:
                window_title = f"Debug Window (Lvl: {current_level}, Top: {game_region['top']})"
                cv2.imshow(window_title, debug_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            if left_x is None:
                continue

            current_left_column = int(left_x / column_width)
            current_right_column = int(right_x / column_width)

            if current_left_column != last_pos_info['left']:
                current_time = time.perf_counter()

                if last_pos_info['left'] != -1:
                    new_direction = 1 if current_left_column > last_pos_info['left'] else -1
                    if new_direction != direction:
                        print(f"Změna směru na: {'doprava' if new_direction == 1 else 'doleva'}")
                        direction = new_direction

                if last_pos_info['time'] > 0:
                    time_diff = current_time - last_pos_info['time']
                    dwell_time_samples.append(time_diff)

                last_pos_info = {'left': current_left_column, 'time': current_time}

                stable_dwell_time, dwell_time_samples = calculate_stable_dwell_time(dwell_time_samples)

                print(f"Stav: {state}, Levý sl: {current_left_column}, Pravý sl: {current_right_column}, Směr: {'doprava' if direction == 1 else 'doleva'}")

                if state == 'SYNC_WAIT_RIGHT':
                    sync_col = current_right_column if 1 <= current_level <= 4 else current_left_column
                    if sync_col >= (NUM_COLUMNS - 1):
                        print("SYNC: Dosažen pravý okraj. Čekám na návrat vlevo.")
                        state = 'SYNC_WAIT_LEFT'
                elif state == 'SYNC_WAIT_LEFT':
                    if current_left_column == 0:
                        print("SYNC: Dosažen levý okraj. Bot je nyní aktivován (ARMED).")
                        state = 'ARMED'

            if state == 'ARMED' and direction == 1 and stable_dwell_time is not None:
                fire_column = int(right_x / column_width)
                trigger_column = config["TARGET_COLUMN"] - config["TRIGGER_COLUMN_OFFSET"]

                if fire_column == trigger_column:
                    target_pixel = (config["TARGET_COLUMN"] * column_width)
                    pixels_to_go = target_pixel - right_x
                    pixels_per_sec = column_width / stable_dwell_time
                    time_to_target_s = pixels_to_go / pixels_per_sec

                    detection_latency_s = config["DETECTION_LATENCY_MS"] / 1000.0
                    predicted_arrival_time = time.perf_counter() + time_to_target_s - detection_latency_s

                    print(f"Pravý kraj v trigger sloupci {fire_column}. Cíl: {config['TARGET_COLUMN']}")
                    print(f"Predikovaný čas dopadu za: {time_to_target_s * 1000:.1f} ms")

                    while time.perf_counter() < predicted_arrival_time: pass

                    print(f"==> MEZERNÍK! (Dávka {config['INPUT_BURST_COUNT']} stisků)")
                    for i in range(config['INPUT_BURST_COUNT']):
                        pyautogui.press('space')
                        time.sleep(config['INPUT_BURST_DELAY_MS'] / 1000.0)

                    # --- RESET ---
                    current_level += 1
                    print("-" * 20)
                    print(f"Akce provedena. Postup na úroveň {current_level}.")

                    if 1 <= current_level <= 5:
                        config = LOW_LEVEL_CONFIG
                        block_color_rgb = BLUE_BLOCK_COLOR_RGB
                    else:
                        config = HIGH_LEVEL_CONFIG
                        block_color_rgb = YELLOW_BLOCK_COLOR_RGB

                    game_region = calculate_game_region(current_level)
                    block_color_bgr = np.array(block_color_rgb[::-1])
                    column_width = game_region['width'] / NUM_COLUMNS
                    print(f"Nové parametry: Oblast={game_region}, Konfigurace={config}")

                    state = 'SYNC_WAIT_RIGHT'
                    dwell_time_samples.clear()
                    print("Aplikuji 3s cooldown a čekám na plnou synchronizaci...")
                    time.sleep(3)

        print("\nKlávesa 'q' stisknuta, bot se ukončuje.")
        if SHOW_DEBUG_WINDOW:
            cv2.destroyAllWindows()

if __name__ == "__main__":
    print("Vítejte v botovi pro skládání věže!")
    print("Před spuštěním prosím nastavte hodnoty v sekci 'NASTAVENÍ BOTA'.")
    print("\nPotřebné knihovny: pip install numpy opencv-python pyautogui keyboard mss")

    # Zeptáme se uživatele, zda chce spustit bota
    run_bot = input("Chcete spustit bota nyní? (ano/ne): ")
    if run_bot.lower() in ['a', 'ano', 'y', 'yes']:
        main()
    else:
        print("Bot nebyl spuštěn. Upravte nastavení a zkuste to znovu.")