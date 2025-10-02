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
#    Zadejte úroveň hry (číslo od 1 do 15).
#    Bot si podle toho sám upraví oblast, kterou snímá.
LEVEL = 1  # Změňte toto číslo podle aktuální úrovně

def calculate_game_region(level: int) -> dict:
    """
    Vrátí souřadnice herní oblasti na základě zvolené úrovně.
    Používá vyhledávací tabulku s přesnými hodnotami 'top' pro každou úroveň.
    """
    # Vyhledávací tabulka pro 'top' souřadnici na základě dat od uživatele
    LEVEL_TOPS = {
        1: 849, 2: 786, 3: 728, 4: 667, 5: 608, 6: 518,
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

# Automatický výběr barvy podle úrovně
if 1 <= LEVEL <= 5:
    BLOCK_COLOR_RGB = BLUE_BLOCK_COLOR_RGB
    print(f"Úroveň {LEVEL}: Používám modrou barvu kostky.")
else:
    BLOCK_COLOR_RGB = YELLOW_BLOCK_COLOR_RGB
    print(f"Úroveň {LEVEL}: Používám žlutou barvu kostky.")

#    Jak moc se může skutečná barva lišit od zadané.
#    Větší číslo znamená větší toleranci (např. pro různé odstíny).
COLOR_TOLERANCE = 25


# 3. HERNÍ PARAMETRY
#    Počet sloupců, mezi kterými kostka přeskakuje.
NUM_COLUMNS = 10

#    CÍLOVÝ SLOUPEC (TARGET_COLUMN)
#    Do kterého sloupce má bot mířit? Čísluje se od 0.
#    Pokud máte 10 sloupců (0 až 9), sloupec 4 je pátý zleva.
#    Toto je nejdůležitější hodnota pro míření.
TARGET_COLUMN = 8


# 4. NASTAVENÍ PRO DYNAMICKÉ ČASOVÁNÍ
#    Tato nastavení řídí novou logiku, která měří rychlost kostky
#    a podle toho předvídá, kdy stisknout mezerník.
# ==============================================================================

#    SPUŠTĚNÍ AKCE (TRIGGER)
#    Kolik sloupců PŘED cílovým sloupcem má bot začít s výpočtem.
#    Pokud je cíl sloupec 8 a TRIGGER_COLUMN_OFFSET = 2, bot se "aktivuje",
#    když kostka dorazí do sloupce 6 (při pohybu zleva doprava).
#    Větší hodnota dává botovi více času na výpočet, ale vyžaduje
#    stabilnější rychlost kostky.
#    Doporučená hodnota: 1 nebo 2.
TRIGGER_COLUMN_OFFSET = 2


#    DÁVKA VSTUPŮ (INPUT BURST)
#    Abychom měli jistotu, že náš stisk hra zaregistruje, pošleme jich
#    několik ve velmi rychlém sledu. Tím pokryjeme případné malé
#    nepřesnosti v časování nebo zpoždění ve hře.

#    Počet stisků v jedné dávce.
#    Doporučená hodnota: 3 až 5.
INPUT_BURST_COUNT = 3

#    Prodleva mezi jednotlivými stisky v dávce (v milisekundách).
#    Cílem je trefit herní okno pro vstup, které je často velmi krátké.
#    Doporučená hodnota: 5 až 10 ms.
INPUT_BURST_DELAY_MS = 7


# 5. KOMPENZACE LATENCE
#    Každý systém má malé zpoždění mezi tím, co se stane na obrazovce,
#    a tím, kdy to náš skript zjistí. Tato hodnota (v milisekundách)
#    se odečte od naměřeného času, aby byly výpočty přesnější.
#    Dobrá startovní hodnota je 10-20 ms. Laďte podle potřeby.
DETECTION_LATENCY_MS = 15


# ==============================================================================
# --- KÓD BOTA ---
# Od této části byste neměli nic měnit, pokud nevíte, co děláte.
# ==============================================================================

# Hodnoty jako BLOCK_COLOR_BGR a COLUMN_WIDTH se nyní počítají v main().

def find_block_column(sct_instance, level: int, game_region: dict, column_width: float, block_color_bgr: np.ndarray):
    """
    Snímá herní obrazovku, najde kostku(y) a vrátí její sloupec a snímek pro ladění.
    - Pro úrovně 1-5: Detekuje skupinu modrých kostek a najde jejich společný střed.
    - Pro úrovně 6-15: Detekuje jednu největší žlutou kostku.
    """
    try:
        img = sct_instance.grab(game_region)
        img_np = np.array(img)
        frame = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
        debug_frame = frame.copy() if SHOW_DEBUG_WINDOW else None

        lower_bound = np.maximum(0, block_color_bgr - COLOR_TOLERANCE)
        upper_bound = np.minimum(255, block_color_bgr + COLOR_TOLERANCE)
        mask = cv2.inRange(frame, lower_bound, upper_bound)

        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, debug_frame

        # Odfiltrujeme malé kontury, které jsou pravděpodobně jen šum
        significant_contours = [c for c in contours if cv2.contourArea(c) > 50]
        if not significant_contours:
            return None, debug_frame

        target_contour_group = None
        # Logika pro úrovně 1-5: Zpracujeme všechny nalezené kostky jako jednu skupinu
        if 1 <= level <= 5:
            target_contour_group = np.vstack(significant_contours)
            if SHOW_DEBUG_WINDOW:
                cv2.drawContours(debug_frame, significant_contours, -1, (0, 255, 0), 2)
        # Logika pro ostatní úrovně: Najdeme jen největší kostku
        else:
            target_contour_group = max(significant_contours, key=cv2.contourArea)
            if SHOW_DEBUG_WINDOW:
                cv2.drawContours(debug_frame, [target_contour_group], -1, (0, 255, 0), 2)

        # Spočítáme střed (moment) z výsledné kontury nebo skupiny kontur
        M = cv2.moments(target_contour_group)
        if M["m00"] == 0:
            return None, debug_frame

        center_x = int(M["m10"] / M["m00"])
        column_index = int(center_x / column_width)

        if SHOW_DEBUG_WINDOW:
            center_y = int(M["m01"] / M["m00"])
            cv2.circle(debug_frame, (center_x, center_y), 5, (0, 0, 255), -1)
            for i in range(1, NUM_COLUMNS):
                line_x = int(i * column_width)
                cv2.line(debug_frame, (line_x, 0), (line_x, game_region['height']), (255, 0, 0), 1)

        return column_index, debug_frame

    except Exception as e:
        print(f"Vyskytla se chyba při zpracování obrazu: {e}")
        return None, None

def main():
    """
    Hlavní smyčka bota s dynamickým měřením rychlosti a prediktivním časováním.
    """
    # --- Inicializace na základě nastavení ---
    game_region = calculate_game_region(LEVEL)
    block_color_bgr = np.array(BLOCK_COLOR_RGB[::-1])
    column_width = game_region['width'] / NUM_COLUMNS

    print("="*50)
    print(f"Úroveň: {LEVEL}, Cílová oblast: {game_region}")
    print("Bot s dynamickým časováním se spouští za 3 sekundy...")
    print("PŘEPNĚTE SE DO OKNA SE HROU!")
    print("Pro ukončení bota stiskněte a držte klávesu 'q'.")
    print("="*50)
    time.sleep(3)

    # --- Stavové proměnné bota ---
    state = 'AWAITING_CYCLE'
    last_column = -1
    direction = 1
    dwell_time_s = None
    column_timestamps = {}

    with mss.mss() as sct:
        while not keyboard.is_pressed('q'):
            # Předáváme všechny potřebné, lokálně vypočítané hodnoty do detekční funkce
            current_column, debug_frame = find_block_column(sct, LEVEL, game_region, column_width, block_color_bgr)

            if SHOW_DEBUG_WINDOW and debug_frame is not None:
                window_title = f"Debug Window (Top: {game_region['top']})"
                cv2.imshow(window_title, debug_frame)
                # Důležité pro zobrazení okna a zpracování událostí
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            if current_column is None:
                continue

            # Detekce změny sloupce je klíčová pro veškerou logiku
            if current_column != last_column:
                detection_time = time.perf_counter()
                # Zohledníme latenci detekce pro přesnější měření
                inferred_detection_time = detection_time - (DETECTION_LATENCY_MS / 1000.0)

                # Aktualizace směru pohybu
                if last_column != -1:
                    new_direction = 1 if current_column > last_column else -1
                    if new_direction != direction:
                        print(f"Změna směru: {'doprava' if new_direction == 1 else 'doleva'}")
                        direction = new_direction

                print(f"Stav: {state}, Sloupec: {current_column}")

                # --- STAV: ČEKÁNÍ NA NOVÝ CYKLUS ---
                if state == 'AWAITING_CYCLE':
                    if current_column == 0:
                        print("Detekován začátek cyklu (sloupec 0). Zahajuji měření rychlosti.")
                        state = 'MEASURING'
                        column_timestamps = {0: inferred_detection_time}

                # --- STAV: MĚŘENÍ RYCHLOSTI ---
                elif state == 'MEASURING':
                    column_timestamps[current_column] = inferred_detection_time

                    # Vypočítáme rychlost z několika po sobě jdoucích skoků
                    if len(column_timestamps) > 3:
                        # Seřadíme sloupce a časy, abychom mohli počítat rozdíly
                        sorted_cols = sorted(column_timestamps.keys())
                        time_diffs = [column_timestamps[sorted_cols[i]] - column_timestamps[sorted_cols[i-1]] for i in range(1, len(sorted_cols))]

                        # Odstraníme případné odlehlé hodnoty (např. při změně směru)
                        stable_diffs = [d for d in time_diffs if d > 0.01]
                        if not stable_diffs:
                            continue

                        dwell_time_s = np.mean(stable_diffs)
                        print(f"Změřena rychlost: {dwell_time_s * 1000:.2f} ms na sloupec.")
                        print("Bot je nyní aktivován a připraven k akci (ARMED).")
                        state = 'ARMED'

                # --- STAV: PŘIPRAVEN K AKCI ---
                elif state == 'ARMED':
                    trigger_column = TARGET_COLUMN - (TRIGGER_COLUMN_OFFSET * direction)

                    if current_column == trigger_column:
                        columns_to_go = abs(TARGET_COLUMN - current_column)
                        time_to_target_s = columns_to_go * dwell_time_s

                        # VÝPOČET ČASU DOPADU:
                        # Náš `detection_time` je čas, kdy kostka *vstoupila* do `trigger_column`.
                        # `time_to_target_s` je doba, za kterou dorazí ke *vstupu* do `TARGET_COLUMN`.
                        # Chceme však stisknout uprostřed doby, kdy je v cílovém sloupci,
                        # proto přičteme polovinu změřeného času na sloupec (`dwell_time_s`).
                        time_to_target_center_s = time_to_target_s + (dwell_time_s / 2.0)
                        predicted_arrival_time = inferred_detection_time + time_to_target_center_s

                        print(f"Kostka v trigger sloupci {current_column}. Cíl: {TARGET_COLUMN}")
                        print(f"Predikovaný čas dopadu za: {(predicted_arrival_time - time.perf_counter()) * 1000:.1f} ms")

                        # Přesné čekání pomocí "busy-wait" smyčky pro maximální přesnost.
                        # Tato metoda je náročnější na CPU, ale zaručuje, že nepropásneme
                        # správný okamžik kvůli nepřesnostem `time.sleep()`.
                        while time.perf_counter() < predicted_arrival_time:
                            pass

                        # --- DÁVKA VSTUPŮ (INPUT BURST) ---
                        print(f"==> MEZERNÍK! (Dávka {INPUT_BURST_COUNT} stisků)")
                        for i in range(INPUT_BURST_COUNT):
                            pyautogui.press('space')
                            # Krátká pauza mezi stisky v dávce
                            time.sleep(INPUT_BURST_DELAY_MS / 1000.0)

                        # Po akci se bot resetuje a čeká na další cyklus
                        print("-" * 20)
                        print("Akce provedena. Čekám na další cyklus od sloupce 0.")
                        state = 'AWAITING_CYCLE'
                        dwell_time_s = None
                        column_timestamps = {}
                        # Krátká pauza, abychom znovu nedetekovali stejnou kostku
                        time.sleep(0.3)

                last_column = current_column

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