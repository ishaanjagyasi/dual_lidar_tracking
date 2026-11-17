// Three tennis balls that repeatedly burst from, then steer back to, the player.
class BallGlitch {
  TennisBall[] balls = new TennisBall[3];
  boolean active = false;

  void start() {
    active = true;
    PVector origin = playerPosition();
    for (int i = 0; i < balls.length; i++) {
      balls[i] = new TennisBall(origin, i);
    }
  }

  void update() {
    if (!active) return;

    PVector target = playerPosition();
    for (int i = 0; i < balls.length; i++) {
      balls[i].update(target);
    }
  }

  void display() {
    if (!active) return;

    for (int i = 0; i < balls.length; i++) {
      balls[i].display();
    }
  }

  void reset() {
    active = false;
  }

  PVector playerPosition() {
    if (user != null && !user.isOffGrid &&
        user.currentRow >= 0 && user.currentRow < grid.rows &&
        user.currentCol >= 0 && user.currentCol < grid.cols) {
      GridCell cell = grid.cells[user.currentRow][user.currentCol];
      return new PVector(cell.x + cellSize / 2.0, cell.y + cellSize / 2.0);
    }

    // Keep following the visible player even when they have stepped outside the grid.
    if (user != null) {
      return new PVector(gridOffsetX + (user.currentCol + 0.5) * cellSize,
                         gridOffsetY + (user.currentRow + 0.5) * cellSize);
    }
    return new PVector(width / 2.0, height / 2.0);
  }
}

class TennisBall {
  PVector position;
  PVector velocity;
  ArrayList<PVector> trail = new ArrayList<PVector>();
  float radius;
  float maxReturnSpeed;
  float seamRotation;
  float[] fleckAngles = new float[7];
  float[] fleckDistances = new float[7];
  int mode;
  int burstEndsAt;

  final int BURSTING = 0;
  final int RETURNING = 1;

  TennisBall(PVector origin, int index) {
    radius = random(24, 32);
    maxReturnSpeed = random(5.2, 7.2);
    position = origin.copy();
    velocity = new PVector();
    for (int i = 0; i < fleckAngles.length; i++) {
      fleckAngles[i] = random(TWO_PI);
      fleckDistances[i] = random(0.18, 0.75);
    }
    // A small stagger prevents the three balls from becoming synchronized.
    launch(origin, index * 140);
  }

  void launch(PVector origin, int stagger) {
    position.set(origin);
    float angle = random(TWO_PI);
    velocity = PVector.fromAngle(angle);
    velocity.mult(random(4.5, 7.5));
    seamRotation = angle;
    mode = BURSTING;
    burstEndsAt = millis() + stagger + (int)random(450, 1050);
    trail.clear();
  }

  void update(PVector target) {
    if (mode == BURSTING) {
      // The outward path remains deliberate; its variation comes from each launch.
      velocity.mult(0.992);
      position.add(velocity);

      if (millis() >= burstEndsAt || isOutsideScreen()) {
        mode = RETURNING;
      }
    } else {
      // Steer toward the player's current position instead of snapping to it.
      PVector desired = PVector.sub(target, position);
      float distance = desired.mag();
      if (distance < radius + 10) {
        launch(target, 0);
        return;
      }

      desired.setMag(maxReturnSpeed);
      PVector steering = PVector.sub(desired, velocity);
      steering.limit(0.10);
      velocity.add(steering);
      velocity.limit(maxReturnSpeed);
      position.add(velocity);
    }

    seamRotation = lerp(seamRotation, velocity.heading(), 0.06);
    trail.add(position.copy());
    if (trail.size() > 4) trail.remove(0);
  }

  boolean isOutsideScreen() {
    return position.x < -radius || position.x > width + radius ||
           position.y < -radius || position.y > height + radius;
  }

  void display() {
    noStroke();
    for (int i = 0; i < trail.size(); i++) {
      float alpha = map(i, 0, trail.size(), 8, 32);
      float size = map(i, 0, trail.size(), radius * 0.65, radius * 1.05);
      fill(169, 171, 84, alpha);
      PVector point = trail.get(i);
      ellipse(point.x, point.y, size, size);
    }

    // Muted felt gives the ball a physical, less cartoon-like presence.
    fill(177, 179, 83);
    ellipse(position.x, position.y, radius * 2, radius * 2);

    // Flecks suggest tennis-ball felt without introducing a shiny game-icon highlight.
    fill(104, 108, 52, 95);
    for (int i = 0; i < fleckAngles.length; i++) {
      float fleckX = position.x + cos(fleckAngles[i] + seamRotation) * radius * fleckDistances[i];
      float fleckY = position.y + sin(fleckAngles[i] + seamRotation) * radius * fleckDistances[i];
      ellipse(fleckX, fleckY, 2.5, 2.5);
    }

    // Curved seams rotate with the ball's movement.
    pushMatrix();
    translate(position.x, position.y);
    rotate(seamRotation);
    noFill();
    stroke(229, 221, 162, 220);
    strokeWeight(3);
    arc(0, 0, radius * 1.45, radius * 1.65, -HALF_PI * 0.78, HALF_PI * 0.78);
    arc(0, 0, radius * 1.45, radius * 1.65, HALF_PI * 1.22, TWO_PI - HALF_PI * 0.78);
    popMatrix();
  }
}
