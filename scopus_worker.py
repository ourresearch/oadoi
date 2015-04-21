import optparse
import rq_worker

if __name__ == '__main__':
    parser = optparse.OptionParser("usage: %prog [options]")
    parser.add_option('-n', '--name', dest='name', type="str", default=None)
    (options, args) = parser.parse_args()
    worker_name = options.name

    print "starting scopus worker for worker {}".format(worker_name)

    rq_worker.start_worker("scopus", worker_name=worker_name)


