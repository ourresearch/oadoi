import rq_worker

if __name__ == '__main__':
    rq_worker.start_worker("github_zip")
