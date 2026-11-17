// automatically called when OSC message is received
//file: OSCReceive.pde
int lastCueCode = -1;

void oscEvent(OscMessage msg) {
  receivingOSC.handleOSC(msg);
}

// Global variable for tile length, will need to adjust this based on physical tile size
float tileLength = 0.5; // 0.5 meters
boolean needsCalibration = false; //wait for new round to start
class OSCReceiveClass {
  float sensorX, sensorY;
  
  //convert user (x,y) posn in mm to tile coordinates
  void handleOSC(OscMessage msg) {
    if (msg.checkAddrPattern("/position")) { 
      if (showingRoundScreen) return; //ignore /position while waiting for max timing cues
      if (msg.checkTypetag("ff")) {
        float rawX = msg.get(0).floatValue();
        float rawY = msg.get(1).floatValue();
        //sensor uses aeronautics coordinate system so we have to swap x and y
        sensorX=rawX; 
        sensorY=rawY;
        
        // Check if we need to calibrate, do this at start of rounds 1 and 2 only
        if (needsCalibration) {
          restartPythonWithReset();
          user.updatePosition(0, 0);  // Reset user to (0,0)
          needsCalibration = false;
          println("Player is now at grid corner (0,0) SENSOR CALIBRATED");
        }
        
        // Convert from mm to m, then divide by physical tile length
        //pos x direction is forwards, pos y direction is right from perspective of user
        float posX = (sensorX / 1000.0) / tileLength;
        float posY = (sensorY / 1000.0) / tileLength;
        
        //sensor debugging variables and y axis flip
        //posY = (gridRows - 1) - posY;
        posY = -posY;
        dbgPosXTiles = posX;
        dbgPosYTiles = posY;
        
        int currentTileY = (int)floor(posY);
        int currentTileX;
        
        if (currentRound == 3) {
          currentTileX = hopView.mapHopscotchCol(currentTileY, posX);
        } else {
          currentTileX = (int)floor(posX);
        }
        
        //debugging trace
        dbgTileX = currentTileX;
        dbgTileY = currentTileY;

        if (SHOW_TRAIL) {
          float px = gridOffsetX + (dbgPosXTiles + 0.5) * cellSize;
          float py = gridOffsetY + (dbgPosYTiles + 0.5) * cellSize;
          dbgTrail.add(new PVector(px, py));
          if (dbgTrail.size() > dbgTrailMax) dbgTrail.remove(0);
        }

        user.updatePosition(currentTileY, currentTileX);
        
        // Print raw sensor data and converted tile coordinates
        println("Raw sensor (mm): X= " + sensorX + ", Y= " + sensorY);
        println("Tile coordinates: X=" + currentTileX + ", Y=" + currentTileY);
      }
    }
    
     // ===== MAX ROUND CUES (latched) =====
    
    if (msg.checkAddrPattern("/level1begins")) {
      int code = int0(msg, 10);
      if (code == 10 && lastCueCode != 10) {
        lastCueCode = 10;
        println("Level 1 Begins");
        //startRoundFromCue(1);
      }
    }
    
    if (msg.checkAddrPattern("/level1ends")) {
      int code = int0(msg, 30);
      if (code == 30 && lastCueCode != 30) {
        lastCueCode = 30;
        println("Level 1 Ends");
        //endRoundFromCue(1);
      }
    }
    
    if (msg.checkAddrPattern("/level2begins")) {
      int code = int0(msg, 50);
      if (code == 50 && lastCueCode != 50) {
        lastCueCode = 50;
        println("Level 2 Begins");
        //startRoundFromCue(2);
      }
    }
    
    if (msg.checkAddrPattern("/level2ends")) {
      int code = int0(msg, 70);
      if (code == 70 && lastCueCode != 70) {
        lastCueCode = 70;
        println("Level 2 Ends");
        //endRoundFromCue(2);
      }
    }
    
    if (msg.checkAddrPattern("/level3begins")) {
      int code = int0(msg, 90);
      if (code == 90 && lastCueCode != 90) {
        lastCueCode = 90;
        println("Level 3 Begins");
        //startRoundFromCue(3);
      }
    }
    
    if (msg.checkAddrPattern("/level3ends")) {
      int code = int0(msg, 110);
      if (code == 110 && lastCueCode != 110) {
        lastCueCode = 110;
        println("Level 3 Ends");
        //endRoundFromCue(3);
      }
    }
    
    if (msg.checkAddrPattern("/gameEnds")) {
      int code = int0(msg, 200);
      if (code == 200 && lastCueCode != 200) {
        lastCueCode = 200;
        println("Game Ends");
        WAIT_FOR_MAX = true;
        roundScreenLabel = "Game Over";
        showingRoundScreen = true;
      }
    }

  }
  
  void restartPythonWithReset() {
    OscMessage myMessage = new OscMessage("/reset");
    oscP5.send(myMessage, pythonResetAddress); // Use pythonResetAddress to send reset command
    println("Reset command sent to Python");
  }
  
  int int0(OscMessage msg, int fallback) {
    try { return msg.get(0).intValue(); }
    catch(Exception e) { return fallback; }
  }

  
}
