import sys, time
sys.path.insert(0, r"C:\Users\Usernom\Documents\Terramine\src")
import device

t = time.time(); p = device.screenshot(); print(f"screenshot      {time.time()-t:.2f}s")
t = time.time(); x, _ = device.dump_ui(); print(f"dump_ui         {time.time()-t:.2f}s  nodes={len(device.parse_nodes(x))}")
t = time.time(); device.tap(540, 1200); print(f"single tap      {time.time()-t:.2f}s")

pts = [(288, 755)] * 10
t = time.time()
for x_, y_ in pts:
    device.adb("shell", "input", "tap", str(x_), str(y_))
print(f"10 taps (loop)  {time.time()-t:.2f}s")

t = time.time()
cmd = "; ".join(f"input tap {x_} {y_}" for x_, y_ in pts)
device.adb("shell", cmd)
print(f"10 taps (batch) {time.time()-t:.2f}s")

t = time.time()
cmd = "; ".join(f"input tap {x_} {y_}" for x_, y_ in pts * 4)
device.adb("shell", cmd)
print(f"40 taps (batch) {time.time()-t:.2f}s")
