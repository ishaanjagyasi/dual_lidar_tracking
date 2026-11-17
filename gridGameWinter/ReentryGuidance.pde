class ReentryGuidance {
  boolean outsideGrid = false;
  boolean invitationVisible = false;
  int targetRow = -1;
  int targetCol = -1;
  int invitationStartTime = 0;
  int invitationFadeDuration = 0;

  boolean appliesToCurrentRound() {
    return currentRound == 1 || currentRound == 2;
  }

  void onExitedGrid() {
    if (!appliesToCurrentRound()) return;

    outsideGrid = true;
    invitationVisible = false;
    targetRow = -1;
    targetCol = -1;
  }

  void onBellHit() {
    if (!outsideGrid || !appliesToCurrentRound() || invitationVisible) return;

    ArrayList<PVector> edgeCells = new ArrayList<PVector>();
    for (int row = 0; row < grid.rows; row++) {
      for (int col = 0; col < grid.cols; col++) {
        if (row == 0 || row == grid.rows - 1 || col == 0 || col == grid.cols - 1) {
          edgeCells.add(new PVector(row, col));
        }
      }
    }

    PVector chosen = edgeCells.get((int)random(edgeCells.size()));
    targetRow = (int)chosen.x;
    targetCol = (int)chosen.y;
    invitationVisible = true;
    invitationStartTime = millis();
    invitationFadeDuration = (int)random(6000, 10000);
  }

  void onReenteredGrid() {
    reset();
  }

  void reset() {
    outsideGrid = false;
    invitationVisible = false;
    targetRow = -1;
    targetCol = -1;
  }

  boolean shouldHideGridInterior() {
    return outsideGrid && appliesToCurrentRound();
  }

  void display() {
    if (!outsideGrid || !appliesToCurrentRound() || !invitationVisible) return;
    if (targetRow < 0 || targetRow >= grid.rows || targetCol < 0 || targetCol >= grid.cols) return;

    GridCell target = grid.cells[targetRow][targetCol];
    float progress = constrain((millis() - invitationStartTime) / (float)invitationFadeDuration, 0, 1);
    float easedProgress = progress * progress * (3 - 2 * progress);
    float pulse = progress >= 1 ? (sin((millis() - invitationStartTime) * 0.004) + 1) * 16 : 0;
    float alpha = lerp(10, 210, easedProgress) + pulse;

    noStroke();
    fill(20, 190, 20, alpha);
    rect(target.x, target.y, target.size, target.size);
  }
}
