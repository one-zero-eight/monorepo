import datetime as dtm


def utcnow() -> dtm.datetime:
    return dtm.datetime.now(dtm.UTC)
