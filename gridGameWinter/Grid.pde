//file: Grid.pde
class Grid {
  int rows;
  int cols;
  int cellSize;
  int offsetX;
  int offsetY;
  GridCell[][] cells;
  GlitchManager glitchManager;
  HashMap<String, Boolean> caughtOverlays; // Glitch visuals held while the performer is off-grid
  ArrayList<String> overlaysExpireOnReturn;
  LetterGlitch lg = new LetterGlitch();
  boolean glitch24WasActive = false;


  Grid(int r, int c, int cs) {
    rows = r;
    cols = c;
    cellSize = cs;
    cells = new GridCell[rows][cols];
    caughtOverlays = new HashMap<String, Boolean>();
    overlaysExpireOnReturn = new ArrayList<String>();

    offsetX = (width - cols * cellSize) / 2;  // X offset to center grid
    offsetY = (height - rows * cellSize) / 2; // Y offset to center grid

    // store info for drawing dashed white lines
    gridOffsetX = offsetX;
    gridOffsetY = offsetY;

    // create glitch manager
    glitchManager = new GlitchManager();

    int currentNumber = 0;
    for (int i = 0; i < rows; i++) {
      for (int j = 0; j < cols; j++) {
        float x = offsetX + j * cellSize;
        float y = offsetY + i * cellSize;
        cells[i][j] = new GridCell(x, y, cellSize, currentNumber++, i, j);
      }
    }

    // Enable glitch tiles per round
    if (currentRound == 1) { // 2 glitching tiles
      enableGlitch(1, 1);
      enableGlitch(3, 4);
    } else if (currentRound == 2) { // 4 glitching tiles
      enableGlitch(2, 0);
      enableGlitch(0, 4);
      enableGlitch(2, 2);
      enableGlitch(4, 4);
    }
  }

  void enableGlitch(int row, int col) {
    if (row >= 0 && row < rows && col >= 0 && col < cols) {
      if (currentRound == 1) {
        // Level 1 has only two eligible tiles, so it can show one or two effects.
        glitchManager.addRandomGlitch(row, col, 10000, 24000,
          3000, 12000, 4000, 16000);
      } else if (currentRound == 2) {
        // Level 2 changes more often; the population manager permits larger overlaps.
        glitchManager.addRandomGlitch(row, col, 8000, 20000,
          3000, 12000, 4000, 16000);
      }
    }
  }

  // Hold a caught glitch visual while the performer is outside the grid.
  void toggleCaughtOverlay(int tileNumber) {
    String key = "tile_" + tileNumber;
    boolean current = caughtOverlays.getOrDefault(key, false);
    boolean next = !current;
    caughtOverlays.put(key, next);
    println("Overlay for tile " + tileNumber + " toggled: " + next);
  }

  // Check if overlay should be displayed
  boolean shouldShowOverlay(int tileNumber) {
    String key = "tile_" + tileNumber;
    return caughtOverlays.getOrDefault(key, false);
  }

  // Mark currently active overlays to expire when user leaves and returns
  void markActiveOverlaysExpireOnReturn() {
    for (String key : caughtOverlays.keySet()) {
      if (caughtOverlays.getOrDefault(key, false)) {
        overlaysExpireOnReturn.add(key);
      }
    }
  }

  // Expire overlays that were marked when the user returns to the grid
  void expireMarkedOverlaysOnReturn() {
    for (String key : overlaysExpireOnReturn) {
      if (caughtOverlays.getOrDefault(key, false)) {
        String numStr = key.substring(key.indexOf('_') + 1);
        int tileNumber = Integer.parseInt(numStr);
        // Clear the caught visual and end any underlying restart before the next cycle.
        caughtOverlays.put(key, false);
        GridCell cell = getCellByNumber(tileNumber);
        if (cell != null) {
          glitchManager.forceExpireGlitchAt(cell.row, cell.col);
        }
      }
    }
    overlaysExpireOnReturn.clear();
  }

  // Clear overlay without scheduling anything
  void clearOverlayForTile(int tileNumber) {
    String key = "tile_" + tileNumber;
    caughtOverlays.put(key, false);
  }

  // Find cell by its sequential tile number
  GridCell getCellByNumber(int tileNumber) {
    for (int r = 0; r < rows; r++) {
      for (int c = 0; c < cols; c++) {
        if (cells[r][c].number == tileNumber) return cells[r][c];
      }
    }
    return null;
  }

  void display() {
    // Update per-cell glitch states via manager
    glitchManager.applyToGrid(this);
    boolean showGridInterior = !reentryGuidance.shouldHideGridInterior();

    // The outer board stays visible off-grid, while its ordinary cell layer clears away.
    if (showGridInterior) {
      for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) {
          cells[i][j].display();
        }
      }

      // Draw adjacent tile highlights
      user.displayAdjacentHighlights();
    }

    // row glitch tile 19
    if (currentRound == 1 && shouldShowOverlay(19)) {
      noStroke();
      int paletteSize = round2Dots.accentPalette.length;
      float progress = (millis() % 4000) / 4000.0;

      for (int i = 0; i < rows; i++) {
        int colorIndex = (i + millis() / 4000) % paletteSize;
        color firstColor = round2Dots.accentPalette[colorIndex];
        color nextColor = round2Dots.accentPalette[(colorIndex + 1) % paletteSize];
        colorMode(HSB, 360, 100, 100);
        float h1 = hue(firstColor);
        float h2 = hue(nextColor);
        fill(lerp(h1, h2, progress), 100, 100);
        colorMode(RGB, 255);
        rect(gridOffsetX, gridOffsetY + i * cellSize, cols * cellSize, cellSize);
      }
    }

    // Full grid glitch overlay (tile 6, round 1 only) - interactive
    if (currentRound == 1 && shouldShowOverlay(6)) {
      web();
    }



    // Full screen blackout (round 2, tile 10). Player avatar still visible.
    if (currentRound == 2 && shouldShowOverlay(10)) {
      noStroke();
      fill(0);
      rect(0, 0, width, height);

      // Version B: supportive silence glitch
      scoreTracker.resetAllScores();
    }

    //glitch tile 24
    if (currentRound == 2 && shouldShowOverlay(24)) {
      if (!glitch24WasActive) {
        lg.reset();
        glitch24WasActive = true;
      }
      if (frameCount % 2 == 0) {
        lg.addLetter();
      }
      lg.display();
    } else {
      glitch24WasActive = false;
    }





    // Pixelated 8 bit glitch (tile 4, round 2)
    if (currentRound == 2 && shouldShowOverlay(4)) {
      int blockSize = (int)random(15, 40); // chunky pixel blocks

      noStroke();
      for (int y = 0; y < height; y += blockSize) {
        for (int x = 0; x < width; x += blockSize) {
          // Random grayscale for 8-bit feel
          fill(random(255));
          rect(x, y, blockSize, blockSize);
        }
      }
    }

    // Tennis-ball glitch (tile 12, round 2)
    if (currentRound == 2 && shouldShowOverlay(12)) {
      if (!ballGlitch.active) {
        ballGlitch.start();
      }
      ballGlitch.update();
    }

    if (ballGlitch.active) {
      ballGlitch.display();
    }

    // Reset whenever the caught tile-12 visual is cleared.
    if (currentRound == 2 && !shouldShowOverlay(12)) {
      if (ballGlitch.active) {
        ballGlitch.reset();
      }
    }

    // TODO: effects for rest of glitches

    boolean flicker = (currentRound < 3) && (user.isOffGrid ||
      (user.currentRow >= 0 && user.currentRow < rows &&
      user.currentCol >= 0 && user.currentCol < cols &&
      cells[user.currentRow][user.currentCol].isGlitching));

    drawGridBorder(flicker);
  }

  // Keep this helper if your OSCSender uses it
  GridCell getCellForLogical(int row, int col) {
    return cells[row][col];
  }

  void drawGridBorder(boolean flicker) {
    if (currentRound >= 3) return; // only rounds 1 and2

    pushStyle();
    noFill();
    boolean flickerNow = flicker && (frameCount % 6 == 0);

    color borderColor;
    if (flickerNow) {
      borderColor = round2Dots.accentPalette[int(random(round2Dots.accentPalette.length))];
    } else {
      borderColor = color(160);
    }

    stroke(borderColor);
    strokeWeight(flickerNow ? random(4, 11) : 7);

    int pad = 18;
    rect(offsetX - pad, offsetY - pad,
      cols * cellSize + 2 * pad, rows * cellSize + 2 * pad);

    popStyle();
  }
  void web() {
    float gridSize = 5 * cellSize;

    // pull point follows the user, even outside the grid
    float ux = gridOffsetX + (user.currentCol + 0.5) * cellSize;
    float uy = gridOffsetY + (user.currentRow + 0.5) * cellSize;

    float reach = gridSize * 0.9;
    float base = 0.55;
    float seg = 6;
    float t = millis() * 0.002;

    blendMode(ADD);
    strokeCap(SQUARE);

    // vertical lines
    for (int i = 0; i <= 5; i++) {
      float gx = gridOffsetX + i * cellSize;
      float pin = (i == 0 || i == 5) ? 0 : 1;
      for (float y = gridOffsetY; y < gridOffsetY + gridSize; y += seg) {
        float taper = sin(PI * (y - gridOffsetY) / gridSize);
        float near = exp(-sq(dist(gx, y, ux, uy)) / sq(reach));
        float pull = max(near, 0.6);   // bend never fades below 60%
        float f = base + (1 - base) * near;
        float x = gx
          + (ux - gx) * pull * 0.3 * taper * pin
          + (noise(i * 10, y * 0.05, t * 3) - 0.5) * 8 * f * taper * pin;
        glitchSeg(x, y, x, y + seg, f, (int)((y - gridOffsetY) / seg));
      }
    }

    // horizontal lines
    for (int i = 0; i <= 5; i++) {
      float gy = gridOffsetY + i * cellSize;
      float pin = (i == 0 || i == 5) ? 0 : 1;
      for (float x = gridOffsetX; x < gridOffsetX + gridSize; x += seg) {
        float taper = sin(PI * (x - gridOffsetX) / gridSize);
        float near = exp(-sq(dist(x, gy, ux, uy)) / sq(reach));
        float pull = max(near, 0.6);
        float f = base + (1 - base) * near;
        float y = gy
          + (uy - gy) * pull * 0.3 * taper * pin
          + (noise(i * 10 + 50, x * 0.05, t * 3) - 0.5) * 8 * f * taper * pin;
        glitchSeg(x, y, x + seg, y, f, (int)((x - gridOffsetX) / seg));
      }
    }

    blendMode(BLEND);
  }

  void glitchSeg(float x1, float y1, float x2, float y2, float f, int idx) {
    // dashed when far, solid when near
    if (f < 0.15 && idx % 2 == 1) return;

    strokeWeight(2 + 3 * f);
    stroke(255, 200 * f);
    line(x1, y1, x2, y2);
  }
}
