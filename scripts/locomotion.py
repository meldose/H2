# Conceptual example — not executable H2 API code

robot = H2MotionClient()

robot.walk(vx=0.2, vy=0.0, yaw_rate=0.0)
sleep(5)

robot.stop()

robot.turn(yaw_rate=0.2)
sleep(3)

robot.stop()