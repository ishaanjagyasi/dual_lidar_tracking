//file: GlitchEffect.pde
// Centralized Glitch objects and manager

class Glitch {
  int row, col;
  int startTime;      // scheduled start time (may be in future due to delay)
  int activeStartTime; // time when glitch actually started flickering (set in update())
  int duration; // ms
  // Respawn support: timed glitches reappear after a random delay.
  boolean respawn;
  int minRespawnDelay; // ms
  int maxRespawnDelay; // ms
  int minDuration;
  int maxDuration;
  int recencyEndsAt = 0;
  boolean missedFired = false;

  Glitch(int r, int c, int dur) {
    row = r;
    col = c;
    startTime = millis();
    activeStartTime = -1; // not active yet
    duration = dur;
    respawn = false;
    minRespawnDelay = 5000;
    maxRespawnDelay = 20000;
  }

  // Returns whether this glitch should currently be visible/flickering
  boolean update(boolean mayStart) {
    int now = millis();

    // If the glitch hasn't started yet (still in delay), return false
    if (now < startTime) {
      return false;
    }

    // Mark the moment the glitch becomes active (for expiry calculation)
    if (activeStartTime == -1) {
      if (!mayStart) return false;

      // --- Prevent glitch activation if user is on this tile and it's not glitching ---
      if (user != null && user.currentRow == row && user.currentCol == col && !grid.cells[row][col].isGlitching) {
        // Postpone activation by resetting startTime
        int delay = (int)random(minRespawnDelay, maxRespawnDelay);
        startTime = now + delay;
        // debug info
        println("Glitch at (" + row + "," + col + ") postponed because user is on tile. New startTime: " + startTime);
        return false;
      }
      activeStartTime = now;
      missedFired = false; // ready to detect miss on next cycle
    }

    return now - activeStartTime < duration;
  }

  boolean started() {
    if (activeStartTime == -1) return false;
    return true;
  }

  void deferStart(int delay) {
    startTime = millis() + delay;
    activeStartTime = -1;
  }

  // Timed glitches expire after their duration (counted from when they actually started).
  boolean expired(Grid g) {
    //println("expired() called, respawn=" + respawn + " activeStartTime=" + activeStartTime); //debugging
    if (activeStartTime == -1) return false; // not active yet, don't expire
    if (millis() - activeStartTime >= duration) {
      if (respawn) {
        if (!missedFired && !grid.shouldShowOverlay(grid.cells[row][col].number)) {
            missedFired = true;
            scoreTracker.onGlitchMiss();
            println("Glitch missed!");
        }
        // A recently ended effect may return, just with a modest preference for
        // the other tiles first. Long memory here made the board go quiet too often.
        recencyEndsAt = millis() + (int)random(10000, 25000);
        if (maxDuration > minDuration) {
          duration = (int)random(minDuration, maxDuration);
        }
        int delay = (int)random(minRespawnDelay, maxRespawnDelay);
        deferStart(delay);
        return false;
      }
      return true;
    }
    return false;
  }
}

class GlitchManager {
  ArrayList<Glitch> glitches;
  // Glitch rounds share an activity climate, but have no fixed rise/crest/fall cycle.
  // Individual glitches still keep their own independent clocks.
  float activityLevel = 0.55;
  float activityTarget = 0.55;
  int lastClimateUpdateAt = -1;
  int nextClimateChangeAt = -1;
  int surgeEndsAt = 0;
  int nextSurgeAt = -1;
  int emptySince = -1;
  int finalCrestWindow = 45000;

  GlitchManager() {
    glitches = new ArrayList<Glitch>();
  }

  boolean isGlitchActive(int row, int col, Grid g) {
    for (Glitch gl : glitches) {
      if (gl.row == row && gl.col == col && !gl.expired(g) && gl.started()) {
        return true;
      }
    }
    return false;
  }

  boolean isPopulationActive(Glitch gl) {
    if (!gl.started()) return false;
    return millis() - gl.activeStartTime < gl.duration;
  }

  int activeGlitchCount() {
    int count = 0;
    for (Glitch gl : glitches) {
      if (isPopulationActive(gl)) count++;
    }
    return count;
  }

  void updateActivityClimate() {
    if (currentRound != 1 && currentRound != 2) return;

    int now = millis();
    if (lastClimateUpdateAt == -1) {
      lastClimateUpdateAt = now;
      activityLevel = random(0.45, 0.65);
      activityTarget = random(0.40, 0.75);
      nextClimateChangeAt = now + (int)random(12000, 28000);
      nextSurgeAt = now + (int)random(20000, 50000);
    }

    if (now >= nextClimateChangeAt) {
      // A random walk changes the overall feeling without announcing a new "wave."
      activityTarget = constrain(activityTarget + random(-0.28, 0.28), 0.30, 0.82);
      nextClimateChangeAt = now + (int)random(12000, 30000);
    }

    if (now >= nextSurgeAt) {
      // Surges are optional, brief opportunities for three or four overlaps.
      if (random(1) < 0.30) {
        surgeEndsAt = now + (int)random(6000, 14000);
      }
      nextSurgeAt = now + (int)random(25000, 65000);
    }

    float elapsed = min(now - lastClimateUpdateAt, 1000) / 1000.0;
    float blend = 1.0 - exp(-elapsed / 10.0);
    activityLevel += (activityTarget - activityLevel) * blend;
    lastClimateUpdateAt = now;
  }

  boolean surgeActive() {
    return millis() < surgeEndsAt;
  }

  float populationPressure() {
    if (currentRound != 1 && currentRound != 2) return 0.0;
    updateActivityClimate();

    float pressure = activityLevel;
    if (surgeActive()) pressure += 0.18;

    // Level 2 still ends at a higher intensity without creating repeated wave shapes.
    int timeRemaining = roundDuration - (millis() - roundStartTime);
    if (currentRound == 2 && timeRemaining <= finalCrestWindow) {
      float finalRise = constrain((finalCrestWindow - timeRemaining) / (float)finalCrestWindow, 0, 1);
      pressure = max(pressure, lerp(0.50, 0.80, finalRise));
    }
    return constrain(pressure, 0, 1);
  }

  float admissionChance(int activeCount, float pressure) {
    if (activeCount == 0) return lerp(0.62, 0.92, pressure);
    if (activeCount == 1) return lerp(0.32, 0.70, pressure);
    if (activeCount == 2) return lerp(0.10, 0.50, pressure);
    if (activeCount == 3) return lerp(0.01, 0.25, pressure);
    return 0.0;
  }

  float repeatFactor(Glitch gl, float pressure) {
    if (millis() < gl.recencyEndsAt) {
      // Repeats remain possible; recency is only a gentle preference, not a ban.
      return lerp(0.65, 1.0, pressure);
    }
    return 1.0;
  }

  int retryDelay(float pressure) {
    return (int)lerp(random(7000, 15000), random(1500, 5000), pressure);
  }

  boolean mayStart(Glitch gl, Grid g) {
    if (gl.started() || millis() < gl.startTime) return true;

    // Let Glitch.update() postpone this case without evaluating a new admission roll.
    if (user != null && user.currentRow == gl.row && user.currentCol == gl.col &&
        !g.cells[gl.row][gl.col].isGlitching) {
      return true;
    }

    float pressure = populationPressure();
    int activeCount = activeGlitchCount();

    float chance = admissionChance(activeCount, pressure) * repeatFactor(gl, pressure);
    if ((currentRound == 1 || currentRound == 2) && activeCount == 0 && emptySince != -1) {
      // Empty moments are allowed, but a long empty board grows increasingly eager
      // to admit the next eligible glitch.
      float quietFor = millis() - emptySince;
      chance = max(chance, map(constrain(quietFor, 6000, 14000), 6000, 14000, 0.70, 0.98));
    }
    if ((currentRound == 1 || currentRound == 2) && random(1) >= chance) {
      gl.deferStart(retryDelay(pressure));
      return false;
    }

    return true;
  }

  // for glitches with random start and end times
  void addRandomGlitch(int row, int col, int minDur, int maxDur,
                       int minDelay, int maxDelay,
                       int minRespawnDelay, int maxRespawnDelay) {
  int dur = (int)random(minDur, maxDur);
  int delay = (int)random(minDelay, maxDelay);
  Glitch g = new Glitch(row, col, dur);
  g.minDuration = minDur;
  g.maxDuration = maxDur;
  g.startTime = millis() + delay; // allow delayed start
  g.respawn = true;
  g.minRespawnDelay = minRespawnDelay;
  g.maxRespawnDelay = maxRespawnDelay;
  glitches.add(g);
}

  // Apply current glitch states to the provided grid (sets each cell's isGlitching)
  void applyToGrid(Grid g) {
    updateActivityClimate();

    if (currentRound == 1 || currentRound == 2) {
      if (activeGlitchCount() == 0) {
        if (emptySince == -1) emptySince = millis();
      } else {
        emptySince = -1;
      }
    }

    // Clear any per-cell glitch flags first
    for (int r = 0; r < g.rows; r++) {
      for (int c = 0; c < g.cols; c++) {
        g.cells[r][c].isGlitching = false;
      }
    }

    // Update glitches and apply their effects; remove expired ones
    for (int i = glitches.size() - 1; i >= 0; i--) {
      Glitch gl = glitches.get(i);

      // Remove invalid glitches that reference out-of-range cells
      if (gl.row < 0 || gl.row >= g.rows || gl.col < 0 || gl.col >= g.cols) {
        glitches.remove(i);
        continue;
      }

      boolean wasStarted = gl.started();
      boolean on = gl.update(mayStart(gl, g));
      // Set isGlitching true for the entire glitch duration
      if (on) {
        g.cells[gl.row][gl.col].isGlitching = true;
      }

      // If the user is off the grid and this tile's overlay is toggled, keep the visual effect on
      int tileNum = g.cells[gl.row][gl.col].number;
      if (user.isOffGrid && g.shouldShowOverlay(tileNum)) {
        g.cells[gl.row][gl.col].isGlitching = true;
      }

      // Call expired() now to let it schedule respawn or indicate removal.
      boolean didExpire = gl.expired(g);

      // A caught overlay is visual-only and stays on while the performer is off-grid.
      if (wasStarted && !gl.started()) {
        if (!(user.isOffGrid && g.shouldShowOverlay(tileNum)) &&
            gl.row >= 0 && gl.row < g.rows && gl.col >= 0 && gl.col < g.cols) {
          g.clearOverlayForTile(tileNum);
        }
      }

      if (didExpire) {
        if (gl.row >= 0 && gl.row < g.rows && gl.col >= 0 && gl.col < g.cols) {
            if (!g.shouldShowOverlay(tileNum) && !gl.missedFired) {
                gl.missedFired = true;
                scoreTracker.onGlitchMiss();
                println("Glitch expired uncaught - miss!");
            }
            g.clearOverlayForTile(tileNum);
        }
        glitches.remove(i);
      }
    }
  }

  // Force a glitch at the specified row/col to expire now and schedule respawn
  void forceExpireGlitchAt(int row, int col) {
    int now = millis();
    for (int i = glitches.size() - 1; i >= 0; i--) {
      Glitch gl = glitches.get(i);
      if (gl.row == row && gl.col == col) {
        // If it's not active yet (scheduled in future), postpone its start
        if (gl.activeStartTime == -1 && millis() < gl.startTime) {
          int delay = (int)random(gl.minRespawnDelay, gl.maxRespawnDelay);
          gl.deferStart(delay);
        } else {
          // Force it to appear expired now so expired() will handle respawn
          gl.missedFired = true;
          gl.activeStartTime = now - gl.duration - 1;
        }
      }
    }
  }

}
