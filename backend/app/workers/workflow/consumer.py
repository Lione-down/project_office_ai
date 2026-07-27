from uuid import UUID


class WorkflowQueueConsumer:
    def __init__(self, queue, worker) -> None:
        self._queue = queue
        self._worker = worker

    async def consume_once(self):
        message = await self._queue.dequeue()
        if message is None:
            return None
        try:
            if message["event_type"] != "brief.generate":
                raise ValueError("workflow queue event type is invalid")
            task_id = UUID(str(message["payload"]["workflow_task_id"]))
        except (KeyError, TypeError, ValueError) as exception:
            raise ValueError("workflow queue message is invalid") from exception
        return await self._worker.process(task_id)


class RedisWorkflowQueue:
    queue_key = "office_ai:workflow:queue"

    def __init__(self, redis, *, timeout_seconds: int = 2) -> None:
        self._redis = redis
        self._timeout_seconds = timeout_seconds

    async def dequeue(self):
        return await self._redis.dequeue_generation(
            self.queue_key,
            timeout_seconds=self._timeout_seconds,
        )
