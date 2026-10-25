"""Run the desktop alignment engine in a cancellable child process."""
import json
import sys

from cueflow.engine import SyncRequest, synchronize

if __name__ == "__main__":
    result = synchronize(SyncRequest(sys.argv[1], sys.argv[2], sys.argv[3]))
    print("CUEFLOW_RESULT " + json.dumps(result), flush=True)
