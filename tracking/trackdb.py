from typing import List, Union
from app import db
from sqlalchemy import text
from sqlalchemy.engine.row import Row

ARXIV_ENDPOINT_ID = "ca8f8d56758a80a4f86"


def query_pmh_record_by_arxiv_id(arxiv_id: str) -> List[Row]:
    arxiv_id_short = arxiv_id.split(":")[-1]
    pmh_id = f"oai:arXiv.org:{arxiv_id_short}"
    sq = """select * from pmh_record where pmh_id like :pmh_id order by id"""
    params = {
        "pmh_id": pmh_id,
    }
    result = db.session.execute(text(sq), params).all()
    return result


def query_page_new_by_arxiv_id(arxiv_id: str) -> List[Row]:
    arxiv_id_short = arxiv_id.split(":")[-1]
    pmh_id = f"{ARXIV_ENDPOINT_ID}:oai:arXiv.org:{arxiv_id_short}"
    sq = """select * from page_new where pmh_id like :pmh_id order by id"""
    params = {
        "pmh_id": pmh_id,
    }
    result = db.session.execute(text(sq), params).all()
    return result


def query_green_scrape_queue_by_page_new_id(page_new_id: str) -> List[Row]:
    sq = """select * from page_green_scrape_queue where id = :page_new_id"""
    params = {
        "page_new_id": page_new_id,
    }
    result = db.session.execute(text(sq), params).all()
    return result
