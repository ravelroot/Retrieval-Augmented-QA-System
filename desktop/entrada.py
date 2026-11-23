import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from nexo.cli import main
    main()
