from db.monocleWrapper import MonocleWrapper
from db.rmWrapper import RmWrapper
from utils.walkerArgs import parseArgs

args = parseArgs()

if args.db_method == "rm":
    db_wrapper = RmWrapper(args)
elif args.db_method == "monocle":
    db_wrapper = MonocleWrapper(args)
else:
    print("Invalid db_method in config. Exiting")
    exit(1)


def main():
    if db_wrapper.download_gym_images():
        print("Successfully downloaded gym images to ocr/gym_img")
    else:
        print("Failed downloading gym images")


if __name__ == '__main__':
    main()
