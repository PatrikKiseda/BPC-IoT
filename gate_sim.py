# garage_simulation.py
import asyncio
import threading
import random

DOOR_OPERATION_TIME = 30
COLLISION_PROBABILITY = 0.01

class DoorState:
    CLOSED = "CLOSED"
    OPENING = "OPENING"
    OPEN = "OPEN"
    CLOSING = "CLOSING"

class GarageDoor:
    def __init__(self):
        self.state = DoorState.CLOSED
        self.position = 0
        self.movement_task = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.lock = threading.Lock()
        self.running = True

    def start(self):
        self.thread.start()

    def stop_simulation(self):
        self.running = False
        self.loop.call_soon_threadsafe(self.loop.stop)

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def toggle(self):
        self.loop.call_soon_threadsafe(asyncio.create_task, self._handle_toggle())

    def get_status(self):
        return self.state

    async def _handle_toggle(self):
        with self.lock:
            if self.state == DoorState.CLOSED:
                await self._open()
            elif self.state == DoorState.OPEN:
                await self._close()
            elif self.state == DoorState.OPENING:
                print("🔁 Reversing to CLOSE")
                self._stop()
                await self._close()
            elif self.state == DoorState.CLOSING:
                print("🔁 Reversing to OPEN")
                self._stop()
                await self._open()

    def _stop(self):
        if self.movement_task:
            self.movement_task.cancel()
        self.movement_task = None

    async def _open(self):
        if self.state == DoorState.OPEN:
            return
        print("🔓 Opening door...")
        self.state = DoorState.OPENING
        self.movement_task = asyncio.create_task(self._move(self.position, 100, DoorState.OPEN))

    async def _close(self):
        if self.state == DoorState.CLOSED:
            return
        print("🔒 Closing door...")
        self.state = DoorState.CLOSING
        self.movement_task = asyncio.create_task(self._move(self.position, 0, DoorState.CLOSED))

    # async def _move(self, start, end, final_state):
    #     duration = abs(end - start) / 100 * DOOR_OPERATION_TIME
    #     direction = "opening" if end > start else "closing"
    #     try:
    #         for step in range(1, 101):
    #             await asyncio.sleep(duration / 100)
    #             self.position = start + (end - start) * step / 100
    #             print(f"🚪 Door position: {self.position:.0f}%")
    #
    #             if direction == "closing" and random.random() < COLLISION_PROBABILITY:
    #                 print("⚠️  Collision detected while closing! Reversing...")
    #                 self._stop()
    #                 await self._open()
    #                 return
    #
    #         self.state = final_state
    #         print(f"✅ Door is now {self.state}")
    #     except asyncio.CancelledError:
    #         print("⏹️  Door movement interrupted.")
    #     finally:
    #         self.movement_task = None

    async def _move(self, start, end, final_state):
        duration = abs(end - start) / 100 * DOOR_OPERATION_TIME
        direction = "opening" if end > start else "closing"
        try:
            for step in range(1, 101):
                await asyncio.sleep(duration / 100)
                self.position = start + (end - start) * step / 100
                self.print_progress_bar(self.position)

                if direction == "closing" and random.random() < COLLISION_PROBABILITY:
                    print("\n⚠️  Collision detected while closing! Reversing...")
                    self._stop()
                    await self._open()
                    return

            self.state = final_state
            print(f"\n✅ Door is now {self.state}")
        except asyncio.CancelledError:
            print("\n⏹️  Door movement interrupted.")
        finally:
            self.movement_task = None

    def print_progress_bar(self, position):
        percent = int(position)
        bar_length = 20
        filled = int(bar_length * percent / 100)
        bar = "█" * filled + "-" * (bar_length - filled)
        print(f"\r🚪 [{bar}] {percent}%", end="", flush=True)