import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from LLManalyzer.splitter import split_file


def test(path):
    print(f"\n=== Testing: {path} ===")
    chunks = split_file(path)
    for c in chunks:
        print(f"[Chunk {c.index}]")
        print("TEXT:", repr(c.text[:200]))  # first 200 chars
        print("META:", c.metadata)
        print("---------")


if __name__ == "__main__":
    files = [
        "gdprfs/test_files/test_llm.txt",
        "gdprfs/test_files/test.csv",
        "gdprfs/test_files/test.xlsx",
        "gdprfs/test_files/test.docx",
        "gdprfs/test_files/test.odt",
        "gdprfs/test_files/test_single.pdf",
        "gdprfs/test_files/test_multi.pdf",
        "gdprfs/test_files/test_middle_empty.pdf",
    ]

    for f in files:
        path = os.path.abspath(f)
        if os.path.exists(path):
            test(path)
        else:
            print(f"File not found: {path}")
