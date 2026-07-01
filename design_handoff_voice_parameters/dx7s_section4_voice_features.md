# Section 4: Using the New Voice Features

---

## Voice Edit Buttons

All of the Voice Mode parameters are adjusted via the LCD displays called up using buttons 7~13 and 23~26. Many of these buttons call up multiple LCD displays.

### Button 7 LCD Display (ALGORITHM)

```
[7]→ ALG 2 111111        → Algorithm (1~32)
     Algorithm select      [111111 = all 6 operators active]

  → ALG 2 111111        → Feedback Level (0~7)
    Feedback     = 7

  → ALG 2 111111        → Oscillator Key Sync (off, on)
    Osc key sync:on

  → ALG18 111111        → Transpose (mid c = c1~c5)
    Middle C  = C2

  → ALG18 111111  L     → Voice Name (10 characters)
    Name :MellowHorn      [L = Large/upper case mode]
    OR
    ALG18 111111  s       [s = small/lower case mode]
    Name :MellowHorn
```

### Button 8 LCD Display (OSCILLATOR)

```
[8]→ ALG 2 111111 OP1    → Oscillator Mode (ratio, fixed)
     Frequency(Ratio)

  → ALG 2 111111 OP1    → Frequency Coarse (varies)
    F-coarse= 1.00

  → ALG 2 111111 OP1    → Frequency Fine (varies)
    F-fine   = 1.00

  → ALG 2 111111 OP1    → Oscillator Detune (-7 ~ +7)
    Osc detune   = 0
```

### Button 9 LCD Display (EG)

```
[9]→ ALG 2 111111 OP1    → Rate Scaling (0~7)
     Rate Scaling = 2

  → ALG 2 111111 OP1    → Envelope Generator Rates 1~4 (0~99)
    EG-R 54 35 19 60

  → ALG 2 111111 OP1    → Envelope Generator Levels 1~4 (0~99)
    EG-L 99 97 94 00
```

### Button 10 LCD Displays (OUTPUT LEVEL)

Two branches depending on Scaling Mode selection:

**Normal Scaling branch:**
```
[10]→ ALG 2 111111 OP1    → Scaling Mode (normal, fractional)
      Scal. mode:nomal

   → ALG 2 111111 OP1    → Output Level (0~99)
     Output level =97

   → ALG 2 111111 OP1    → Break Point (A-1~C8 by half steps)
     Break point= A-1

   → ALG 2 111111 OP1    → Left Curve (-lin, -exp, +lin, +exp)
     L-curve    =-LIN

   → ALG 2 111111 OP1    → Right Curve (-lin, -exp, +lin, +exp)
     R-curve    =-LIN

   → ALG 2 111111 OP1    → Left Depth (0~99)
     L-depth    = 0

   → ALG 2 111111 OP1    → Right Depth (0~99)
     R-depth    = 0
```

**Fractional Scaling branch:**
```
   → ALG 2 111111 OP1    → Scaling Mode (normal, fractional)
     Scal. mode:frac.

   → ALG 2 111111 OP1    → Fractional Scaling Offset (-127~+127)
     OF=+ 0 C*-1=251       Scaling Level For Key Range (0~255)
```

### Button 11 LCD Display (SENSITIVITY)

```
[11]→ ALG 2 111111 OP1   → Key Velocity (0~7)
      Key velocity = 1

   → ALG 2 111111 OP1   → Amplitude Modulation Sensitivity (0~7)
     A mod sens.  = 0

   → ALG 2 111111        → Pitch Modulation Sensitivity (0~7)
     P mod sens.  = 2
```

### Button 12 LCD Display (LFO)

```
[12]→ ALG 2 111111        → LFO Wave
      LFO wave:Triangl       (triangle, saw down, saw up, square, sine, s/hold)

   → ALG 2 111111        → LFO Speed (0~99)
     LFO speed    =30

   → ALG 2 111111        → LFO Delay (0~99)
     LFO delay    = 0

   → ALG 2 111111        → LFO Mode (single, multi)
     LFO mode:Multi

   → ALG 2 111111        → LFO Pitch Modulation Depth (0~99)
     LFO PM depth = 0

   → ALG 2 111111        → LFO Amplitude Modulation Depth (0~99)
     LFO AM depth = 0

   → ALG 2 111111        → LFO Key Sync (off, on)
     LFO key sync:off
```

### Button 13 LCD Display (PITCH EG)

```
[13]→ ALG 2 111111        → Pitch Envelope Octave Range (1/2, 1, 2, 8)
      PEG range:  8oct

   → ALG 2 111111        → Pitch Envelope Velocity (off, on)
     PEG velocity:off

   → ALG 2 111111        → Pitch Envelope Rate Scaling (0~7)
     PEG scaling = 0

   → ALG 2 111111        → Pitch Envelope Rates 1~4 (0~99)
     PEGR 99 95 95 99

   → ALG 2 111111        → Pitch Envelope Levels 1~4 (0~99)
     PEGL 50 48 50 50
```

### Button 23 LCD Displays (KEY MODE)

```
[23]→ Voice edit           → Key Mode Assign
      KeyMode:Poly            (polyphonic, monophonic, unison poly, unison mono)

   → Voice edit           → Unison Detune (0~7)
     Unison detune= 0       (appears only when Key Mode = unison poly or unison mono)
```

### Button 24 LCD Displays (PITCH BEND/PORTAMENTO)

```
[24]→ Voice edit           → Pitch Bend Mode (normal, lowest, highest, key on)
      PB mode:Normal

   → Voice edit           → Pitch Bend Range (0~12)
     P-bend range = 2

   → Voice edit           → Pitch Bend Step (0~12)
     P-bend step  = 0

   → Voice edit           → Portamento Mode
     Sus-Key P retain        (Poly: sus-key, p retain, sus-key p follow)
                             (Mono: fingered porta, full time porta)

   → Voice edit           → Portamento Time (0~99)
     Porta time   = 0

   → Voice edit           → Portamento Step (0~99)
     Porta step   = 0

   → Voice edit           → Random Pitch (0~7)
     Random pitch = 2
```

### Button 25 LCD Displays (BC MW/AT)

```
[25]→ Voice edit           → Breath Controller Pitch Modulation Depth (0~99)
      BC PM depth = 0

   → Voice edit           → Breath Controller Amplitude Modulation Depth (0~99)
     BC AM depth = 0

   → Voice edit           → Breath Controller EG Bias (0~99)
     BC EG-bias  = 0

   → Voice edit           → Breath Controller Pitch Bias (-50~+50)
     BC P-bias  =+ 0

   → Voice edit           → Aftertouch Pitch Modulation Depth (0~99)
     AT PM depth = 0

   → Voice edit           → Aftertouch Amplitude Modulation Depth (0~99)
     AT AM depth = 0

   → Voice edit           → Aftertouch EG Bias (0~99)
     AT EG-bias  =63

   → Voice edit           → Aftertouch Pitch Bias (-50~+50)
     AT P-bias  =+ 0

   → Voice edit           → Modulation Wheel Pitch Modulation Depth (0~99)
     MW PM depth =31

   → Voice edit           → Modulation Wheel Amplitude Modulation Depth (0~99)
     MW AM depth = 0

   → Voice edit           → Modulation Wheel EG Bias (0~99)
     MW EG-bias  = 0
```

### Button 26 LCD Displays (FC1/FC2)

```
[26]→ Voice edit           → Foot Controller 1 to Control Slider 1 (off, on)
      FC1 --> CS1 :off

   → Voice edit           → Foot Controller 1 Pitch Modulation Depth (0~99)
     FC1 PM depth = 0

   → Voice edit           → Foot Controller 1 Amplitude Modulation Depth (0~99)
     FC1 AM depth = 0

   → Voice edit           → Foot Controller 1 EG Bias (0~99)
     FC1 EG-bias  = 0

   → Voice edit           → Foot Controller 1 Volume (0~99)
     FC1 volume   = 0

   → Voice edit           → Foot Controller 2 Pitch Modulation Depth (0~99)
     FC2 PM depth = 0

   → Voice edit           → Foot Controller 2 Amplitude Modulation Depth (0~99)
     FC2 AM depth = 0

   → Voice edit           → Foot Controller 2 EG Bias (0~99)
     FC2 EG-bias  = 0

   → Voice edit           → Foot Controller 2 Volume (0~99)
     FC2 volume  =99

   → Voice edit           → MIDI Controller Pitch Modulation Depth (0~99)
     MC PM depth  = 0

   → Voice edit           → MIDI Controller Amplitude Modulation Depth (0~99)
     MC AM depth  = 0

   → Voice edit           → MIDI Controller EG Bias (0~99)
     MC EG-bias   = 0

   → Voice edit           → MIDI Controller Volume (0~99)
     MC volume    = 0
```

---

## Basic Voice Editing Functions

### Operator Select

The parameters accessed using buttons 8~11 are adjustable for each of the six operators. While editing Voice data, buttons 1~6 provide a quick way to move from one operator to another. The number of the operator that has been chosen will appear in the upper right corner of the LCD.

### Operator On/Off

In order to adjust the settings for the six operators accurately, it is useful to focus on the sound of certain operators by turning off the output of ones not being edited. While editing Voice data, buttons 17~22 provide a quick way to turn the six operators on and off.

[DIAGRAM: Two rows of operator control buttons with arrows pointing to a sample LCD. Upper button row shows OPERATOR SELECT (buttons 1–6) plus button 7 (VOICE/ALGO). Lower row shows OPERATOR ON/OFF (buttons 17–22) plus button 23 (VOICE/KEYM). A sample LCD shows:
`ALG 2 111011 OP1 / F-coarse= 1.00`
The "111011" indicator shows OP3 (position 3 from left) is turned off (shown as 0), while operators 1, 2, 4, 5, and 6 are on (shown as 1).]

The on/off status of the six operators is shown in the center of the upper line of the LCD. When all six operators are turned on, you will see 111111. When an operator is turned off, a 0 will appear in the corresponding position.

### EG Copy

The EG Copy function from the original DX7 is retained in the DX7s, and is made easier through the use of buttons 1~6. Once you have envelope data you want to copy displayed in the LCD, simply press and hold the Store/EG Copy button. You can then choose the copy destination using buttons 1~6.

---

## New Voice Parameters

The basic voice of the DX7s is almost exactly the same as that of the original DX7, assuring complete compatibility between the old and new instruments.

### Pitch Envelope

The Pitch Envelope operates as it did in the original DX7, but some new features have been added. The potential depth of the Pitch Envelope effect can now be adjusted using the Range parameter:

| Range | Maximum Pitch Change Range |
|-------|--------------------------|
| 1/2 | 6 semitones |
| 1 | 1 octave |
| 2 | 2 octaves |
| 8 | 8 octaves |

[DIAGRAM: Representative Pitch Envelope Generator shape graph. X-axis = Time, Y-axis = Level (0 at bottom, 50 at middle, 99 at top). Shows: At "Key on," level starts at L4 (bottom, near 0), rises quickly through Rate R1 to Level L1 (above 50 = near 99), falls through Rate R2 to Level L2 (below 50), rises through Rate R3 to Level L3 (just below 99), and continues at that level until "Key off" is triggered, then falls through Rate R4 to L4 (near 0). All four rates and levels labeled.]

In addition, the Velocity parameter allows you to control the intensity of the Pitch Envelope with keyboard touch. There is also a scaling parameter that lets you change the speed of the pitch envelope as you move up the keyboard.

### LFO

There was only one LFO in the original DX7, so all voices were affected in exactly the same way by the LFO settings. In the DX7s, there are sixteen LFOs, one for each voice. Even though all sixteen LFOs must have the same settings, they can now operate independently of each other if the LFO Mode parameter is set to Multi. If Mode is set to Single, the LFO will operate as it did in the original DX7.

### Key Modes

The DX7s provides four Key Modes, accessible using button 23:

- **Polyphonic:** The standard mode. The DX7s can produce up to 16 simultaneous notes.
- **Monophonic:** Only one note can sound at a time.
- **Unison Poly:** Multiple notes can be played, but for each key depressed, multiple voices are stacked together for a thicker sound.
- **Unison Mono:** Only one note at a time, but multiple voices are stacked.

When Unison Poly or Unison Mono is selected, the Unison Detune parameter (0~7) becomes available to create subtle pitch variations between the stacked voices.

---

## Voice Controllers

### Function Data and Voice Effect Data

The DX7s has an expanded set of parameters that govern the behavior of controllers during voice playback. These are accessed via buttons 23~26. (See the LCD display charts above.)

### Pitch Bend Modes

The DX7s offers four Pitch Bend Modes:

- **Normal:** Standard pitch bend behavior.
- **Lowest:** Only the lowest held note is pitch-bent.
- **Highest:** Only the highest held note is pitch-bent.
- **Key on:** Only notes attacked after the bend begins are affected.

### Foot Controller 1 and 2

Foot Controller 1 can optionally be routed to Control Slider 1 (set via the FC1→CS1 parameter in button 26 displays). This allows a foot controller to govern the same real-time FM parameters that can be assigned to the continuous slider.

### Pitch Bias

Pitch Bias (available for Breath Controller and Aftertouch, range -50~+50) shifts the pitch of the voice up or down, modulated by the controller. Unlike Pitch Modulation Depth (which produces vibrato-like pitch change), Pitch Bias sets a persistent offset while the controller is active.

---

## Fractional Scaling

One of the most important aspects of DX7 voicing is Level Scaling, which allows adjustment of each operator's output over the range of the keyboard. The DX7s offers the possibility of even more subtle control over operator outputs, through Fractional Scaling.

### Fractional Scaling and Level Scaling

Although the DX7's Level Scaling offers a great deal of interaction between timbre and frequency, Fractional Scaling offers even greater precision. The level can be set independently in groups of three notes, over the entire range of the keyboard. To provide even more control, the resolution of the level settings has been expanded from 0~99 to 0~255.

[DIAGRAM: Bar chart showing the full keyboard range along the bottom, with Level (0~255) on the vertical axis. A dashed horizontal line at 255 marks the maximum level. Each group of three keys on the keyboard has a shaded vertical bar of varying height representing the independently set operator output level for that note group. A dashed line on the right side is labeled "Offset" — the overall baseline level value from which all per-group levels are measured.]

### Fractional Scaling Editing and Storage

**Entering Fractional Scaling Edit Mode:**

**Step 1:** Press the **VOICE** button.
**Step 2:** Press the **EDIT** button.
**Step 3:** Press the **Output Level button (#10)** to access the Scaling mode LCD display.
**Step 4:** Press the **+1/YES** button to select Fractional Scaling Mode (called "frac" in the LCD display).
**Step 5:** Press the **Output Level button (#10)** again to access the Fractional Scaling Edit LCD display.

**Editing Fractional Scaling Data:**

1. Press the **right cursor button** to select the Note Group Edit parameter.
2. Use the **Operator Select buttons (#1~6)** to choose the operator whose scaling you wish to edit.
3. Press and hold a key in the note group you wish to edit, then press either the Voice button or the INT/CRT button. The note group you have selected will be shown next to the blinking cursor in the LCD.
   - OR: Use the Voice and INT/CRT buttons as left and right cursors to move the desired note group into position next to the blinking cursor in the LCD.
4. Use the data entry slider or the +1/-1 buttons to edit the value for the selected note group.

**Storing Fractional Scaling Data:**

1. Make sure that a properly formatted Cartridge (FKS-Y) is inserted in the cartridge port.
2. Press the **VOICE** button.
3. Press and hold the **STORE** button.
4. Use the number buttons to select the desired memory location. NOTE: The Fractional Scaling data will be linked to the Internal Performance memory with the same location number.
5. While still holding the Store button, press the **+1/YES** button.

---

