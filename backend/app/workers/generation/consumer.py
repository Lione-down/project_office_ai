from uuid import UUID


class GenerationQueueConsumer:
    def __init__(self, queue, worker, executor) -> None:
        self._queue = queue
        self._worker = worker
        self._executor = executor

    async def consume_once(self):
        message = await self._queue.dequeue()
        if message is None:
            return None
        try:
            task_id = UUID(str(message["payload"]["task_id"]))
        except (KeyError, TypeError, ValueError) as exception:
            raise ValueError("generation queue message is invalid") from exception
        return await self._worker.process(task_id, self._executor)


class RedisGenerationQueue:
    queue_key = "office_ai:generation:queue"

    def __init__(self, redis, *, timeout_seconds: int = 2) -> None:
        self._redis = redis
        self._timeout_seconds = timeout_seconds

    async def dequeue(self):
        return await self._redis.dequeue_generation(
            self.queue_key, timeout_seconds=self._timeout_seconds
        )
