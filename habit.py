"""habit - 终端习惯打卡小工具。纯标准库，数据存本地 JSON。"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

VERSION = "0.1.0"
DEFAULT_DATA = os.path.expanduser("~/.config/habit.json")
LOG_DAYS = 14


def load_data(path):
    if not os.path.exists(path):
        return {"habits": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"error: 数据文件损坏或不可读：{path}（{e}）", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict) or "habits" not in data:
        print(f"error: 数据文件格式不对：{path}", file=sys.stderr)
        sys.exit(2)
    return data


def save_data(path, data):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        print(f"error: 日期格式不对（应为 YYYY-MM-DD）：{s}", file=sys.stderr)
        sys.exit(2)


def today(args):
    if args.date:
        return parse_date(args.date)
    return date.today()


def iso_week_of(d):
    monday = d - timedelta(days=d.weekday())
    return monday


def week_count(days, ref):
    monday = iso_week_of(ref)
    return sum(1 for ds in days if monday <= parse_date(ds) < monday + timedelta(days=7))


def streak(days, ref):
    dayset = set(days)
    s = 0
    d = ref
    # 允许今天还没打卡：从昨天开始数也算连续
    if d.isoformat() not in dayset:
        d = d - timedelta(days=1)
    while d.isoformat() in dayset:
        s += 1
        d = d - timedelta(days=1)
    return s


def bar(done, target, width=10):
    if target <= 0:
        return "─" * width
    filled = min(width, int(done / target * width))
    return "█" * filled + "░" * (width - filled)


def cmd_add(args):
    data = load_data(args.data)
    name = args.name
    if name in data["habits"]:
        print(f"error: 习惯已存在：{name}", file=sys.stderr)
        sys.exit(1)
    target = args.target or 0
    if target < 0:
        print("error: 每周目标不能为负数", file=sys.stderr)
        sys.exit(2)
    data["habits"][name] = {"target": target, "created": today(args).isoformat(), "days": {}}
    save_data(args.data, data)
    t = f"，每周目标 {target} 次" if target else ""
    print(f"已添加习惯：{name}{t}")


def cmd_done(args):
    data = load_data(args.data)
    name = args.name
    if name not in data["habits"]:
        print(f"error: 没有这个习惯：{name}（先用 add 添加）", file=sys.stderr)
        sys.exit(1)
    ds = today(args).isoformat()
    days = data["habits"][name]["days"]
    if ds in days:
        print(f"今天已经打过卡了：{name}（{ds}）")
    else:
        days[ds] = True
        save_data(args.data, data)
        print(f"打卡成功：{name}（{ds}）")


def cmd_list(args):
    data = load_data(args.data)
    ref = today(args)
    habits = data["habits"]
    if not habits:
        print("还没有习惯。用 habit add \"习惯名\" 先添加一个。")
        return
    print(f"===== 习惯打卡（{ref.isoformat()}）=====\n")
    for name, h in habits.items():
        days = h.get("days", {})
        wc = week_count(days, ref)
        st = streak(days, ref)
        target = h.get("target", 0)
        prog = f" {bar(wc, target)} {wc}/{target if target else '–'}" if target else f" 本周 {wc} 次"
        print(f"  {name}{prog}　连续 {st} 天")
    print()


def cmd_log(args):
    data = load_data(args.data)
    name = args.name
    if name not in data["habits"]:
        print(f"error: 没有这个习惯：{name}", file=sys.stderr)
        sys.exit(1)
    ref = today(args)
    days = set(data["habits"][name].get("days", {}).keys())
    cells = []
    labels = []
    for i in range(LOG_DAYS - 1, -1, -1):
        d = ref - timedelta(days=i)
        cells.append("▓" if d.isoformat() in days else "░")
        labels.append(str(d.day))
    print(f"===== {name} 最近 {LOG_DAYS} 天 =====")
    print("  " + " ".join(cells))
    print("  " + " ".join(f"{l:>2}" for l in labels))
    print(f"  共打卡 {len([c for c in cells if c == '▓'])} 天")


def cmd_rm(args):
    data = load_data(args.data)
    name = args.name
    if name not in data["habits"]:
        print(f"error: 没有这个习惯：{name}", file=sys.stderr)
        sys.exit(1)
    if not args.yes:
        try:
            ans = input(f"确定删除习惯「{name}」及其全部打卡记录吗？[y/N] ")
        except EOFError:
            ans = ""
        if ans.strip().lower() not in ("y", "yes"):
            print("已取消。")
            return
    del data["habits"][name]
    save_data(args.data, data)
    print(f"已删除：{name}")


def add_common(p):
    p.add_argument("--data", default=DEFAULT_DATA, help="数据文件路径（默认 ~/.config/habit.json）")
    p.add_argument("--date", default=None, help="覆盖“今天”（YYYY-MM-DD，仅用于测试）")


def main(argv=None):
    p = argparse.ArgumentParser(prog="habit", description="终端习惯打卡小工具")
    p.add_argument("--version", action="version", version=f"habit {VERSION}")
    sub = p.add_subparsers(dest="cmd")

    pa = sub.add_parser("add", help="添加习惯")
    pa.add_argument("name", help="习惯名")
    pa.add_argument("--target", type=int, default=0, help="每周目标次数（默认 0 = 不设目标）")
    add_common(pa)

    pd = sub.add_parser("done", help="今日打卡")
    pd.add_argument("name", help="习惯名")
    add_common(pd)

    pl = sub.add_parser("list", help="习惯一览")
    add_common(pl)

    pg = sub.add_parser("log", help="最近 14 天打卡条")
    pg.add_argument("name", help="习惯名")
    add_common(pg)

    pr = sub.add_parser("rm", help="删除习惯")
    pr.add_argument("name", help="习惯名")
    pr.add_argument("--yes", action="store_true", help="跳过确认")
    add_common(pr)

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        sys.exit(2)
    {"add": cmd_add, "done": cmd_done, "list": cmd_list,
     "log": cmd_log, "rm": cmd_rm}[args.cmd](args)


if __name__ == "__main__":
    main()
