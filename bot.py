# Tento skript je bot pro hru, kde stavíte věž z kostek.
# Bot dynamicky měří rychlost pohybující se kostky a na základě toho
# přesně předvídá, kdy stisknout mezerník pro umístění kostky.

import time
import keyboard
import numpy as np
import cv2
import mss
import pyautogui

# ==============================================================================
# --- NASTAVENÍ BOTA ---
# Tuto část můžete upravit podle vaší hry a obrazovky.
# ==============================================================================

# 1. OBLAST HRY (GAME_REGION)
#    Základní hodnoty pro 'left', 'width', 'height' jsou nastaveny podle Levelu 6.
#    Hodnota 'top' se dynamicky mění podle zvoleného levelu.
GAME_REGION = {'left': 660, 'top': 518, 'width': 603, 'height': 64}


# 2. BARVA KOSTKY (BLOCK_COLOR_RGB)
#    Zadejte barvu kostky, kterou má bot hledat.
BLOCK_COLOR_RGB = (236, 168, 44)
COLOR_TOLERANCE = 25


# 3. HERNÍ PARAMETRY
NUM_COLUMNS = 10
TARGET_COLUMN = 8


# 4. POKROČILÉ NASTAVENÍ PRO ČASOVÁNÍ
# ==============================================================================

#    PŘEDVÍDÁNÍ (PREDICTION_OFFSET)
#    Kolik sloupců PŘED cílovým sloupcem má bot reagovat.
PREDICTION_OFFSET = 1

#    KOMPENZACE LATENCE (DETECTION_LATENCY_MS)
#    Odhad, kolik milisekund uplyne mezi skutečným skokem kostky a jeho
#    detekcí skriptem. Tato hodnota se odečte od času detekce, aby se
#    zpřesnil výpočet. Laďte po malých krůčcích.
DETECTION_LATENCY_MS = 15

#    ZPOŽDĚNÍ STISKU (PRESS_DELAY_MS_AFTER_JUMP)
#    Kolik milisekund má bot počkat po PŘEDPOVĚZENÉM skoku do cílového
#    sloupce, než stiskne mezerník.
PRESS_DELAY_MS_AFTER_JUMP = 10

#    DÁVKA VSTUPŮ (INPUT BURST)
INPUT_BURST_COUNT = 3
INPUT_BURST_DELAY_MS = 7


# 5. DEBUG OKNO
#    Pokud nastavíte na True, zobrazí se okno, které v reálném čase ukazuje,
#    co bot "vidí". Užitečné pro ladění.
SHOW_DEBUG_WINDOW = True

# ==============================================================================
# --- KÓD BOTA ---
# Od této části byste neměli nic měnit.
# ==============================================================================

BLOCK_COLOR_BGR = np.array(BLOCK_COLOR_RGB[::-1])
COLUMN_WIDTH = GAME_REGION['width'] / NUM_COLUMNS

def find_block_column(sct_instance):
    """
    Snímá herní obrazovku, najde kostku a vrátí index jejího sloupce.
    Pokud je zapnuté debug okno, vizualizuje detekci.
    """
    try:
        img = sct_instance.grab(GAME_REGION)
        img_np = np.array(img)
        frame = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)

        lower_bound = np.maximum(0, BLOCK_COLOR_BGR - COLOR_TOLERANCE)
        upper_bound = np.minimum(255, BLOCK_COLOR_BGR + COLOR_TOLERANCE)
        mask = cv2.inRange(frame, lower_bound, upper_bound)

        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        column_index = None
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)

            if area >= 50:
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    column_index = int(center_x / COLUMN_WIDTH)
                    if SHOW_DEBUG_WINDOW:
                        cv2.drawContours(frame, [largest_contour], -1, (0, 255, 0), 2)
                        center_y = int(M["m01"] / M["m00"])
                        cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)

        if SHOW_DEBUG_WINDOW:
            cv2.imshow("Bot Vision - Debug", frame)
            cv2.waitKey(1)

        return column_index

    except Exception as e:
        print(f"Vyskytla se chyba při zpracování obrazu: {e}")
        if SHOW_DEBUG_WINDOW:
            cv2.destroyAllWindows()
        return None

def main():
    """
    Hlavní smyčka bota s dynamickým měřením rychlosti a prediktivním časováním.
    """
    print("="*50)
    print("Bot s dynamickým časováním se spouští za 3 sekundy...")
    print("PŘEPNĚTE SE DO OKNA SE HROU!")
    print("Pro ukončení bota stiskněte a držte klávesu 'q'.")
    print("="*50)
    time.sleep(3)

    # --- Stavové proměnné ---
    last_column = -1
    direction = 1
    action_taken = False
    dwell_time_s = None
    column_timestamps = {}
    is_calibrated = False
    is_synced = False  # Zajišťuje, že začneme měřit až od začátku cyklu

    print("Čekám na synchronizaci (detekce kostky ve sloupci 0)...")

    with mss.mss() as sct:
        while not keyboard.is_pressed('q'):
            current_column = find_block_column(sct)

            if current_column is None:
                if action_taken:
                    print("-" * 20 + "\nAkce dokončena. Čekám na nový cyklus pro synchronizaci.")
                    action_taken = False
                    last_column = -1
                    is_calibrated = False
                    is_synced = False # Resetujeme synchronizaci
                    column_timestamps = {}
                    dwell_time_s = None
                continue

            if not is_synced:
                if current_column == 0:
                    print("Synchronizováno! Zahajuji kalibraci rychlosti.")
                    is_synced = True
                    column_timestamps = {}
                    last_column = -1
                else:
                    continue

            if current_column != last_column:
                detection_time = time.perf_counter()
                latency_s = DETECTION_LATENCY_MS / 1000.0
                inferred_jump_start_time = detection_time - latency_s

                if last_column != -1:
                    new_direction = 1 if current_column > last_column else -1
                    if direction != new_direction:
                        direction = new_direction
                        print(f"Změna směru: {'doprava' if direction == 1 else 'doleva'}")
                        is_calibrated = False
                        is_synced = False
                        column_timestamps = {}
                        print("Změna směru, čekám na novou synchronizaci...")
                        last_column = current_column
                        continue

                column_timestamps[current_column] = inferred_jump_start_time

                if not is_calibrated and len(column_timestamps) > 2:
                    sorted_cols = sorted(column_timestamps.keys())
                    time_diffs = [column_timestamps[sorted_cols[i]] - column_timestamps[sorted_cols[i-1]] for i in range(1, len(sorted_cols))]
                    stable_diffs = [d for d in time_diffs if 0.001 < d < 1.0]
                    if len(stable_diffs) > 1:
                        dwell_time_s = np.mean(stable_diffs)
                        is_calibrated = True
                        print(f"Bot je zkalibrován. Rychlost: {dwell_time_s * 1000:.2f} ms/sloupec.")

                if is_calibrated and not action_taken:
                    prediction_trigger_column = TARGET_COLUMN - (PREDICTION_OFFSET * direction)
                    if current_column == prediction_trigger_column:
                        jumps_to_go = PREDICTION_OFFSET
                        time_to_target_s = jumps_to_go * dwell_time_s
                        predicted_target_jump_time = inferred_jump_start_time + time_to_target_s
                        press_delay_s = PRESS_DELAY_MS_AFTER_JUMP / 1000.0
                        target_press_time = predicted_target_jump_time + press_delay_s

                        print(f"Kostka v trigger sloupci {current_column}. Cíl: {TARGET_COLUMN}")
                        print(f"Predikovaný čas stisku za: {((target_press_time - time.perf_counter()) * 1000):.1f} ms")

                        while time.perf_counter() < target_press_time:
                            pass

                        print(f"==> MEZERNÍK! (Dávka {INPUT_BURST_COUNT} stisků)")
                        for i in range(INPUT_BURST_COUNT):
                            pyautogui.press('space')
                            time.sleep(INPUT_BURST_DELAY_MS / 1000.0)

                        action_taken = True

                last_column = current_column

    print("\nKlávesa 'q' stisknuta, bot se ukončuje.")
    if SHOW_DEBUG_WINDOW:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    print("Vítejte v botovi pro skládání věže!")
    print("Před spuštěním prosím nastavte hodnoty v sekci 'NASTAVENÍ BOTA'.")

    level = 0
    while True:
        try:
            level_input = input("Zadejte level, který chcete hrát (1-15): ")
            level = int(level_input)
            if 1 <= level <= 15:
                break
            else:
                print("Chyba: Zadejte prosím číslo od 1 do 15.")
        except ValueError:
            print("Chyba: Zadejte prosím platné číslo.")

    # Mapa 'top' souřadnic pro každý level
    LEVEL_TOPS = {
        1: 819, 2: 756, 3: 698, 4: 637, 5: 578,
        6: 518, 7: 791, 8: 729, 9: 669, 10: 611,
        11: 552, 12: 491, 13: 432, 14: 374, 15: 312
    }

    GAME_REGION['top'] = LEVEL_TOPS[level]

    print(f"Úspěšně nastaven level {level}.")
    print(f"Herní oblast pro tento level: {GAME_REGION}")

    run_bot = input("Chcete spustit bota nyní? (ano/ne): ")
    if run_bot.lower() in ['a', 'ano', 'y', 'yes']:
        main()
    else:
        print("Bot nebyl spuštěn. Upravte nastavení a zkuste to znovu.")