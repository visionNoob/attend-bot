import datetime
import logging
import random
from typing import Iterable, Optional

from flask import request, jsonify
from pytz import utc

from slack_bot import app, supported_channels, KST, db, lines
from slack_bot.models import User, Attendance

NEWLINE = "\n"


def get_message(
    date: datetime,
    username: str,
    quote: str,
    attendances: Optional[Iterable[Attendance]] = None,
) -> str:
    """Returns Slack formatted message

    Args:
        date: Datetime object where 출첵 is done.
        username: Username
        quote: 맨 마지막에 추가할 인용 문구

    Returns:
        A message sent to the user
        :param attendances:
    """
    # 윈도우에서는 strftime을 이용하여 날짜형태를 변경하고 한글을 결합할 경우
    # UnicodeEncodeError 및 Invalid format string 오류가 발생할 수 있습니다.
    # Korean + time.strftime() 문제해결을 위해 다음의 링크를 참고하였습니다.
    # https://hcid-courses.github.io/TA/QnA/issues_with_windows_korean_strftime.html
    datetime_msg = (
        date.strftime(
            "%m월 %d일 출근시간은 한국시각기준 %H시 %M분입니다.".encode("unicode-escape").decode()
        )
        .encode()
        .decode("unicode-escape")
    )

    if attendances:
        attendance_list = []

        for idx, att in enumerate(attendances):
            attendance_list.append(
                f"{idx + 1}. {att.user.username} {att.timestamp.astimezone(KST).strftime('%H:%M')}"
            )

        return f"""*{username}님 출석체크*
    {datetime_msg}

    {NEWLINE.join(attendance_list)}

    {quote}
    """

    return f"""*{username}님 출석체크*
{datetime_msg}

{quote}
"""


@app.route("/healthcheck", methods=["GET"])
def healthcheck():
    return "ok"


def get_channel_names(channel_names: Iterable[str]) -> str:
    """Returns comma separated names after switching to channel.

    Args:
        channel_names: channel names

    Returns:
        It returns a string that all channel names are concatenated.

    >>> get_channel_names({ "attend", "channel1" })
    "#attend, #channel1"
    """
    return ", ".join(map(lambda name: f"#{name}", channel_names))


@app.route("/attend", methods=["POST"])
def attend():
    logging.info("Received request.form = %s", request.form)

    channel_name = request.form.get("channel_name")

    app.logger.info(channel_name)

    if channel_name not in supported_channels:
        return f"출석체크는 다음 채널에서만 사용 가능합니다: {get_channel_names(supported_channels)}"

    now = datetime.datetime.utcnow()
    kr_time: datetime.datetime = utc.localize(now).astimezone(KST)

    text = request.form.get("text")

    attendances = None

    if text == "test":
        user_id = request.form.get("user_id")
        user_name = request.form.get("user_name")

        u: Optional[User] = User.query.filter(User.id == user_id).first()

        if u is None:
            u = User(id=user_id, username=user_name)
            db.session.add(u)
            db.session.commit()

        a = Attendance(timestamp=kr_time, user_id=user_id)
        db.session.add(a)
        db.session.commit()

        attendances = Attendance.get_earliest_n(5, kr_time.date())

    msg = {
        "response_type": "in_channel",
        "text": get_message(
            kr_time,
            request.form.get("user_name"),
            random.choice(lines),
            attendances=attendances,
        ),
    }

    logging.info("Sending a response back %s", msg)

    return jsonify(msg)