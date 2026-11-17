//file: User.pde

class User {
  int currentRow = 0;
  int currentCol = 0;
  boolean isOffGrid = false;

  // bell opportunity latch 
  boolean bellOpportunityActive = false;
  boolean endTile22Active = false;
  
  // Adjacent tile highlight
  int lastPositionChangeTime = 0;
  int highlightDelayMs = 50; // ms before showing adjacent highlights 
  float highlightBaseAlpha = 80; // faint highlight base
  color highlightColor = color(100); // light blue
  // Pulsing / fade parameters
  float highlightPulseSpeed = 0.6; // cycles per second
  float highlightPulseAmp = 40;    // additional alpha from pulse (0..amp)
  int highlightFadeMs = 800;       // fade-in time once highlights appear (ms)

  User() {
    grid.cells[currentRow][currentCol].isUserHere = true;
    lastPositionChangeTime = millis();
  }

  // Call when 'b' is pressed
  void tryBellHit() {
    // Only counts if there is an active bell opportunity
    if (!bellOpportunityActive) return;

    bellOpportunityActive = false;
    scoreTracker.onBellHit();
    if (isOffGrid) reentryGuidance.onBellHit();
    println("Bell hit! successPoints=" + scoreTracker.successPoints);
  }

  // Update position directly from sensor coordinates
  void updatePosition(int newRow, int newCol) {
    boolean caughtGlitch = false;
    boolean outOfBounds = newRow < 0 || newRow >= grid.rows || newCol < 0 || newCol >= grid.cols;
    if (isRestrictedColumnRound && newCol != 2) outOfBounds = true;
  
    // Prevent double-counting when sensor repeats the same tile
    boolean sameTileAndState =
      (newRow == currentRow) && (newCol == currentCol) && (outOfBounds == isOffGrid);
    if (sameTileAndState) return;
  
    boolean wasOffGrid = isOffGrid;
  
    clearCurrentPosition();
  
    currentRow = newRow;
    currentCol = newCol;
    isOffGrid = outOfBounds;
    lastPositionChangeTime = millis(); // reset highlight timer
  
    if (isOffGrid) {
      // Entering off-grid starts a bell opportunity (once per excursion)
      if (!wasOffGrid) {
        bellOpportunityActive = true;
        scoreTracker.onOffGridEntered();  
        // Mark currently active overlays to expire when user returns
        grid.markActiveOverlaysExpireOnReturn();
        reentryGuidance.onExitedGrid();
      }
      endTile22Active = false;
      println("User is OFF-GRID at position (" + newRow + ", " + newCol + ")");
      return;
    }
  
    // On-grid
    grid.cells[currentRow][currentCol].isUserHere = true;
  
    // Round 3: tile 22 boosts both metrics when stepped on
    boolean onEndTile22 = false;
    if (currentRound == 3 && grid.cells[currentRow][currentCol].number == 22) {
      onEndTile22 = true;
    }
  
    if (onEndTile22 && !endTile22Active) {
      bellOpportunityActive = false;
      scoreTracker.onBellHit();
      println("Round 3 end tile 22 hit");
    }
  
    endTile22Active = onEndTile22;
  
    // If returning from off-grid, expire overlays that were marked to expire
    if (wasOffGrid) {
      reentryGuidance.onReenteredGrid();
      grid.expireMarkedOverlaysOnReturn();
    }
  
    if (grid.glitchManager.isGlitchActive(currentRow, currentCol, grid)) {
      int tileNumber = grid.cells[currentRow][currentCol].number;
      grid.toggleCaughtOverlay(tileNumber);
      bellOpportunityActive = false;
      caughtGlitch = true;
      scoreTracker.onBellHit();
    }
    
    printCurrentPosition();
  }

  void clearCurrentPosition() {
    if (!isOffGrid) {
      if (currentRow >= 0 && currentRow < gridRows && currentCol >= 0 && currentCol < gridCols) {
        grid.cells[currentRow][currentCol].isUserHere = false;
      }
    }
  }

  void displayAdjacentHighlights() {
    if (isOffGrid || millis() - lastPositionChangeTime < highlightDelayMs) {
      return; // don't show highlights yet
    }

    // Check all 4 adjacent tiles
    int[][] adjacent = {
       {currentRow - 1, currentCol},     // up
      {currentRow + 1, currentCol},     // down
      {currentRow, currentCol - 1},     // left
      {currentRow, currentCol + 1},     // right
      {currentRow - 1, currentCol - 1}, // up-left
      {currentRow - 1, currentCol + 1}, // up-right
      {currentRow + 1, currentCol - 1}, // down-left
      {currentRow + 1, currentCol + 1}  // down-right
    };

    noStroke();

    // Compute elapsed time since highlight became eligible
    int elapsed = millis() - lastPositionChangeTime;
    float afterDelay = elapsed - highlightDelayMs;
    if (afterDelay < 0) return; 

    // Fade-in factor (0..1)
    float fadeFactor = 1.0;
    if (afterDelay < highlightFadeMs) {
      fadeFactor = afterDelay / (float)highlightFadeMs;
    }

    // Time in seconds used for pulsing
    float t = afterDelay / 1000.0;
    float pulse = (sin(TWO_PI * highlightPulseSpeed * t) + 1) * 0.5 * highlightPulseAmp; // 0..amp

    float finalAlpha = (highlightBaseAlpha + pulse) * fadeFactor;

    fill(red(highlightColor), green(highlightColor), blue(highlightColor), finalAlpha);

    for (int[] pos : adjacent) {
      int adjRow = pos[0];
      int adjCol = pos[1];

      if (adjRow >= 0 && adjRow < grid.rows && adjCol >= 0 && adjCol < grid.cols) {
        GridCell adjCell = grid.cells[adjRow][adjCol];
        rect(adjCell.x, adjCell.y, adjCell.size, adjCell.size);
      }
    }
  }

  // Keep avatar visible even off-grid 
  void display() {
    float x, y;
  
    // If on-grid and the cell exists, draw at the cell's actual center
    if (!isOffGrid
        && currentRow >= 0 && currentRow < grid.rows
        && currentCol >= 0 && currentCol < grid.cols
        && grid.cells[currentRow][currentCol].number >= 0) {
  
      GridCell c = grid.cells[currentRow][currentCol];
      x = c.x + cellSize / 2.0;
      y = c.y + cellSize / 2.0;
  
    } else {
      // Off-grid: fall back to grid-relative position so it's still visible
      x = gridOffsetX + (currentCol + 0.5) * cellSize;
      y = gridOffsetY + (currentRow + 0.5) * cellSize;
    }
  
    fill(0, 0, 0, 25);
    noStroke();
    ellipse(x + 3, y + 3, cellSize / 2, cellSize / 2);
     color hotpink = color(240, 55, 165);
    fill(hotpink,200);
    stroke(0, 120);
    strokeWeight(2);
    ellipse(x, y, cellSize / 2, cellSize / 2);
  }

  void printCurrentPosition() {
    if (!isOffGrid && currentRow >= 0 && currentRow < gridRows && currentCol >= 0 && currentCol < gridCols) {
      int cellIndex = grid.cells[currentRow][currentCol].number;
      println("User is on cell at row " + currentRow + ", column " + currentCol + " (" + cellIndex + ")");
    }
  }
}
