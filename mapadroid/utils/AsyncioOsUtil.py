import asyncio
import concurrent.futures
import os


class AsyncioOsUtil:
    @staticmethod
    async def isfile(path: str) -> bool:
        if not path:
            return False
        loop = asyncio.get_running_loop()
        #with concurrent.futures.ThreadPoolExecutor() as pool:
        file_present: bool = await loop.run_in_executor(
            None, os.path.isfile, path)
        return file_present
