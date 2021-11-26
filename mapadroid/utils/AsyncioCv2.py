import asyncio

import cv2


class AsyncioCv2:
    """
    Util wrapping the Cv2 calls in asyncio ThreadPoolExecutor-usage
    """

    @staticmethod
    async def imread(path: str):
        if not path:
            return None
        loop = asyncio.get_running_loop()
        # with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(
            None, cv2.imread, path)

    @staticmethod
    async def imwrite(path: str, image):
        if not path:
            return None
        loop = asyncio.get_running_loop()
        # with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(
            None, cv2.imwrite, path, image)

    @staticmethod
    async def cvtColor(src, code, dst=None, dstCn: int = 0):
        loop = asyncio.get_running_loop()
        # with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(
            None, cv2.cvtColor, src, code, dst, dstCn)

    @staticmethod
    async def GaussianBlur(src, ksize, sigmaX, dst=None, sigmaY: int = 0, borderType: int = cv2.BORDER_DEFAULT):
        loop = asyncio.get_running_loop()
        # with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(
            None, cv2.GaussianBlur, src, ksize, sigmaX, dst, sigmaY, borderType)

    @staticmethod
    async def Canny(image, threshold1: float, threshold2: float, edges=None, apertureSize: int = 3):
        loop = asyncio.get_running_loop()
        # with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(
            None, cv2.Canny, image, threshold1, threshold2, edges, apertureSize)

    # TODO: Tests comparing results to opencv
    @staticmethod
    async def HoughLinesP(image, rho: float, theta: float, threshold: int, lines=None,
                          minLineLength: float = 0, maxLineGap: float = 0):
        raise ValueError("Do not use for now")
        loop = asyncio.get_running_loop()
        # with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(
            None, cv2.HoughLinesP, image, rho, theta, threshold, lines, minLineLength, maxLineGap)

    @staticmethod
    async def morphologyEx(src, op, kernel, dst=None, anchor=None, iterations: int = 1,
                           borderType=cv2.BORDER_CONSTANT, borderValue=None):
        raise ValueError("Do not use for now")
        loop = asyncio.get_running_loop()
        # with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(
            None, cv2.morphologyEx, src, op, kernel, dst, anchor, iterations, borderType, borderValue)

    @staticmethod
    async def HoughCircles(image, method, dp, minDist, circles=None, param1: int = 100, param2: int = 100,
                           minRadius: int = 0,
                           maxRadius: int = 0):
        loop = asyncio.get_running_loop()
        # with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(
            None, cv2.HoughCircles, image, method, dp, minDist, circles, param1, param2, minRadius, maxRadius)
