"""
通用月度全月业绩预测报告生成器 (完整完美修复版)
"""
import argparse
import calendar
import io
import json
import os
import sys
import re
from collections import defaultdict
from datetime import datetime
import pandas as pd

BASE = r'c:\Users\40321\CodeBuddy\20260507093400'

# 原始 sales 导出文件的列位置
COL_BRAND, COL_CAT1, COL_CAT2, COL_PROJ, COL_DATE, COL_AMT, COL_FLOOR = 2, 3, 4, 5, 7, 14, 22

DOW_CN = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
CAL_HEADERS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

CAT1_OVERRIDE = {'永辉超市': '超市', '幸福蓝海(OMNIJOI)': '影院'}
EXCLUDE_COMM_BRANDS = {'星巴克', '胡子大厨', '小米之家'}
EXCLUDE_COMM_CAT2 = {'钟表/珠宝/高端笔/精品'}


def default_month_file(base, year, month):
    for p in (os.path.join(base, f'{year}年{month}月.xlsx'),
              os.path.join(base, '月会周会分析文件', f'{year}年{month}月.xlsx'),
              os.path.join(base, '月度业绩预估', f'{year}年{month}月.xlsx')):
        if os.path.exists(p):
            return p
    return os.path.join(base, f'{year}年{month}月.xlsx')


def clean_name(name):
    if pd.isna(name): return ""
    return re.sub(r'\s+', '', str(name)).upper()


def parse_finance_data(finance_file):
    """读取单张财务报表，智能匹配并清洗数据"""
    finance_dict = {}
    if not os.path.exists(finance_file):
        return {}

    df = pd.read_excel(finance_file)

    # 智能匹配列名
    col_brand = next((c for c in df.columns if '品牌' in str(c)), None)
    col_pos = next((c for c in df.columns if '资源' in str(c) or '铺位' in str(c)), None)
    col_area = next((c for c in df.columns if '面积' in str(c)), None)
    col_open = next((c for c in df.columns if '实际开业' in str(c) or '开业' in str(c)), None)
    col_rent_price = next((c for c in df.columns if '保底' in str(c) and '单价' in str(c)), None)
    col_share = next((c for c in df.columns if '抽成比例' in str(c)), None)

    for _, r in df.iterrows():
        brand = clean_name(r.get(col_brand, ''))
        if not brand: continue
        pos = clean_name(r.get(col_pos, ''))

        # 面积
        try:
            area = float(r[col_area]) if col_area and pd.notna(r[col_area]) else 0.0
        except ValueError:
            area = 0.0

        # 保底总金额 = 单价 * 面积
        try:
            rent_price = float(r[col_rent_price]) if col_rent_price and pd.notna(r[col_rent_price]) else 0.0
            base_rent = rent_price * area
        except ValueError:
            base_rent = 0.0

        # 👇 核心：清洗抽成比例
        raw_share = str(r[col_share]).strip() if col_share and pd.notna(r[col_share]) else '0'
        if '~' in raw_share:
            raw_share = raw_share.split('~')[0].strip()  # 取左侧 12

        raw_share = raw_share.replace('%', '')  # 如果有 % 就删掉

        try:
            comm_share = float(raw_share)
            # 👇 防呆机制：如果填的是 0.12 这种小数，自动转成 12
            if 0 < comm_share <= 1.0 and '.' in raw_share:
                comm_share = comm_share * 100
        except ValueError:
            comm_share = 0.0

        # 开业日期
        open_date_str = ""
        if col_open and pd.notna(r[col_open]):
            try:
                open_date_str = pd.to_datetime(r[col_open]).strftime('%Y-%m-%d')
            except:
                open_date_str = str(r[col_open])

        key = f"{brand}_{pos}"
        finance_dict[key] = {
            'area': area,
            'rent': base_rent,
            'comm_share': comm_share,
            'threshold': 0.0,  # 没门槛就全额抽
            'resource_pos': pos,
            'open_date': open_date_str
        }
    return finance_dict


def parse_monthly(filepath, year, month, project=None):
    if not os.path.exists(filepath):
        raise SystemExit(f'[ERROR] 数据文件不存在: {filepath}')
    df = pd.read_excel(filepath, header=None, skiprows=1)

    if len(df.columns) <= COL_AMT:
        raise ValueError(f"表格格式错误：当前只有 {len(df.columns)} 列，无法读取第 {COL_AMT} 列的数据。请检查导出格式！")

    test_amt = pd.to_numeric(df[COL_AMT], errors='coerce')
    if test_amt.notna().sum() == 0:
        raise ValueError(f"数据提取失败：第 {COL_AMT} 列（营业额）全是非数字，可能列发生了位移，请检查导出模板！")

    if COL_PROJ in df.columns and project:
        df = df[df[COL_PROJ] == project].copy()

    df[COL_AMT] = pd.to_numeric(df[COL_AMT], errors='coerce')
    df[COL_DATE] = df[COL_DATE].astype(str)
    brand_day, day_totals = {}, {}

    for _, r in df.iterrows():
        name = str(r[COL_BRAND]).strip()
        if not name or name == 'nan': continue
        val = r[COL_AMT]
        if pd.isna(val) or val <= 0: continue
        dt = str(r[COL_DATE]).split(' ')[0]
        if not dt.startswith(str(year)): continue

        floor_str = str(r[COL_FLOOR]).strip() if pd.notna(r[COL_FLOOR]) else '未知'

        if name not in brand_day:
            brand_day[name] = {
                'name': name,
                'cat1': CAT1_OVERRIDE.get(name, str(r[COL_CAT1]).strip()),
                'cat2': str(r[COL_CAT2]).strip(),
                'floor': floor_str, 'floors_set': set(), 'total': 0, 'days': {},
            }
        brand_day[name]['floors_set'].add(floor_str)
        brand_day[name]['days'][dt] = brand_day[name]['days'].get(dt, 0) + val
        brand_day[name]['total'] += val
        day_totals[dt] = day_totals.get(dt, 0) + val

    return {
        'brand_day': brand_day, 'day_totals': day_totals,
        'total': sum(v['total'] for v in brand_day.values()),
        'dates': sorted(day_totals.keys()),
    }


def cat_totals(filepath, project=None):
    if not os.path.exists(filepath): return {}, {}, 0
    df = pd.read_excel(filepath, header=None, skiprows=1)
    if COL_PROJ in df.columns and project:
        df = df[df[COL_PROJ] == project].copy()
    df[COL_AMT] = pd.to_numeric(df[COL_AMT], errors='coerce')
    c1, c2, tot = defaultdict(float), defaultdict(float), 0.0
    for _, r in df.iterrows():
        n = str(r[COL_BRAND]).strip()
        if not n or n == 'nan' or n in ('商铺名', '合计', '序号'): continue
        v = r[COL_AMT]
        if pd.isna(v) or v <= 0: continue
        tot += v
        c1[CAT1_OVERRIDE.get(n, str(r[COL_CAT1]).strip()) or '其他'] += v
        c2[str(r[COL_CAT2]).strip() or '其他'] += v
    return dict(c1), dict(c2), tot


def load_comm_map(filepath):
    comm = {}
    if not filepath or not os.path.exists(filepath): return comm
    wb = pd.read_excel(filepath, header=None)
    for _, r in wb.iterrows():
        n = str(r[1]).strip() if pd.notna(r[1]) else ''
        if not n or n == 'nan': continue
        rate_str = str(r[7]).strip() if pd.notna(r[7]) else '0'
        rate = 0.0
        if rate_str and rate_str not in ('0', '0%', 'nan', '抽成率'):
            s = rate_str.replace('%', '').strip()
            try:
                rate = float(s.split('~')[0]) if '~' in s else (float(s.split('-')[0]) if '-' in s else float(s))
            except ValueError:
                rate = 0.0
        try:
            th = float(r[8]) if pd.notna(r[8]) and str(r[8]).strip() not in ('', 'nan', '抽成临界点(万)') else 0.0
        except ValueError:
            th = 0.0
        if rate > 0 or th > 0: comm[n] = {'rate': rate, 'threshold': th}
    return comm


def detect_comm_file(base):
    d = os.path.join(base, '月会周会分析文件')
    if not os.path.isdir(d): return None
    cands = [os.path.join(d, f) for f in os.listdir(d) if '抽成租金计算公式' in f and f.endswith('.xlsx')]
    return max(cands, key=os.path.getmtime) if cands else None


def dow_stats(day_totals, year, month, skip=()):
    sums, cnts = [0.0] * 7, [0] * 7
    for ds, v in day_totals.items():
        if ds in skip: continue
        try:
            d = datetime.strptime(ds, '%Y-%m-%d').date()
        except ValueError:
            continue
        if (d.year, d.month) != (year, month): continue
        i = d.weekday()
        sums[i] += v;
        cnts[i] += 1
    return {'avgs': [sums[i] / cnts[i] if cnts[i] > 0 else 0.0 for i in range(7)], 'cnts': cnts, 'sums': sums}


def same_period_total(month_data, year, month, days):
    return sum(month_data['day_totals'].get(f'{year}-{month:02d}-{d:02d}', 0) for d in days)


def build_report(args):
    y, m = args.year, args.month
    ndays = calendar.monthrange(y, m)[1]

    d_cur = parse_monthly(args.cur_file, y, m, args.project)
    d_prev = parse_monthly(args.prev_file, *args.prev_ym, args.project)
    d_yoy = parse_monthly(args.yoy_file, *args.yoy_ym, args.project)

    # 👇 替换成单表读取
    fin_file = args.cur_file.replace(".xlsx", "_财务.xlsx")
    finance_dict = parse_finance_data(fin_file)

    cur_days = sorted(int(d.split('-')[2]) for d in d_cur['dates'])
    actual_total = d_cur['total']
    actual_cnt = len(cur_days)

    prev_sp = same_period_total(d_prev, *args.prev_ym, cur_days)
    yoy_sp = same_period_total(d_yoy, *args.yoy_ym, cur_days)
    rt_mom = (actual_total / prev_sp - 1) * 100 if prev_sp > 0 else 0.0
    rt_yoy = (actual_total / yoy_sp - 1) * 100 if yoy_sp > 0 else 0.0

    exclude = set(args.exclude_dates or [])
    boost_info, boost_dates = [], {}
    for spec in (args.boost or []):
        try:
            lhs, rhs = spec.split('=')
            fest, base_spec = rhs.split('/')
        except ValueError:
            raise SystemExit(f'[ERROR] --boost 格式应为 日期=去年节日日/去年基准日，收到: {spec}')
        key = lhs.strip()
        fd = datetime.strptime(fest.strip(), '%Y-%m-%d').date()
        bd = datetime.strptime(base_spec.strip(), '%Y-%m-%d').date()
        fest_v = d_yoy['day_totals'].get(str(fd), 0)
        base_v = d_yoy['day_totals'].get(str(bd), 0)
        ratio = (fest_v / base_v) if base_v > 0 else 1.4
        boost_dates[key] = ratio
        boost_info.append(
            {'date': key, 'fest': str(fd), 'base': str(bd), 'fest_v': fest_v, 'base_v': base_v, 'ratio': ratio})

    cur_dow = dow_stats(d_cur['day_totals'], y, m, skip=exclude)
    prev_dow = dow_stats(d_prev['day_totals'], *args.prev_ym)
    exclude_sum = sum(d_cur['day_totals'].get(d, 0) for d in exclude)

    wd_ids = [i for i in range(5)]
    remain_days = [d for d in range(1, ndays + 1) if d not in cur_days]
    rem_wd = sum(1 for d in remain_days if datetime(y, m, d).weekday() < 5)
    rem_we = len(remain_days) - rem_wd

    est_daily = [0.0] * 7
    for i in range(7):
        est_daily[i] = cur_dow['avgs'][i] if cur_dow['cnts'][i] > 0 else prev_dow['avgs'][i]

    scale = 1.0
    if args.normalize:
        wd_avg = sum(cur_dow['sums'][i] for i in wd_ids) / max(1, sum(cur_dow['cnts'][i] for i in wd_ids))
        we_avg = sum(cur_dow['sums'][i] for i in (5, 6)) / max(1, sum(cur_dow['cnts'][i] for i in (5, 6)))
        lock = rem_wd * (wd_avg or prev_dow['avgs'][0]) + rem_we * (we_avg or prev_dow['avgs'][5])
        raw = sum(est_daily[datetime(y, m, d).weekday()] for d in remain_days)
        scale = lock / raw if raw > 0 else 1.0

    cal_days = {}
    for d in range(1, ndays + 1):
        ds = f'{y}-{m:02d}-{d:02d}'
        dow = datetime(y, m, d).weekday()
        is_actual = ds in d_cur['day_totals']
        if is_actual:
            amt = d_cur['day_totals'][ds]
        elif ds in boost_dates:
            if est_daily[dow] > 0:
                ref_idx = datetime.strptime([b for b in boost_info if b['date'] == ds][0]['fest'],
                                            '%Y-%m-%d').date().weekday()
                amt = est_daily[dow] + (boost_dates[ds] - 1) * est_daily[ref_idx]
            else:
                amt = 0.0
        else:
            amt = est_daily[dow] * scale
        cal_days[d] = {'dow': dow, 'amt': amt, 'is_actual': is_actual, 'is_excluded': ds in exclude,
                       'is_boost': ds in boost_dates}

    boost_extra = sum(
        (cal_days[int(d.split('-')[2])]['amt'] - est_daily[datetime.strptime(d, '%Y-%m-%d').weekday()] * scale) for d in
        boost_dates)
    total_est = sum(v['amt'] for v in cal_days.values())
    remaining = total_est - actual_total
    target = float(args.target or 0)
    gap = target - total_est

    brands = {}
    for name, b in d_prev['brand_day'].items():
        brands[name] = {'name': name, 'cat1': b['cat1'], 'cat2': b['cat2'], 'floor': b['floor'],
                        'prev_actual': b['total'], 'cur_actual': 0.0, 'prev_floors': b['floors_set'],
                        'yoy_actual': d_yoy['brand_day'].get(name, {}).get('total', 0.0), 'days': {}}
    for name, b in d_cur['brand_day'].items():
        if name in brands:
            brands[name]['cur_actual'] = b['total']
            brands[name]['cat1'] = b['cat1'] or brands[name]['cat1']
            brands[name]['cat2'] = b['cat2'] or brands[name]['cat2']
            brands[name]['floor'] = b['floor'] or brands[name]['floor']
        else:
            brands[name] = {'name': name, 'cat1': b['cat1'], 'cat2': b['cat2'], 'floor': b['floor'],
                            'prev_actual': 0.0, 'cur_actual': b['total'], 'prev_floors': set(),
                            'yoy_actual': d_yoy['brand_day'].get(name, {}).get('total', 0.0)}
        brands[name]['days'] = b['days']
        brands[name]['cur_floors'] = b['floors_set']

    for b in brands.values():
        b['cat1'] = CAT1_OVERRIDE.get(b['name'], b['cat1'])

    # 👇 极简重构：彻底解决缩进问题
    share_sum = 0.0
    for b in brands.values():
        b['share'] = b['cur_actual'] / actual_total if actual_total > 0 and b['cur_actual'] > 0 else 0.0
        share_sum += b['share']

    rest_share = 1 - share_sum
    prev_total_rest = sum(b['prev_actual'] for b in brands.values() if b['share'] == 0 and b['prev_actual'] > 0)

    for b in brands.values():
        if b['share'] == 0 and b['prev_actual'] > 0 and prev_total_rest > 0:
            b['share'] = b['prev_actual'] / prev_total_rest * rest_share
        b['estimate'] = b['cur_actual'] + b['share'] * remaining

    for b in brands.values():
        b_clean_name = clean_name(b['name'])
        actual_floors = b.get('cur_floors', ['未知'])
        matched_finance = None
        for floor in actual_floors:
            key = f"{b_clean_name}_{clean_name(floor)}"
            if key in finance_dict:
                matched_finance = finance_dict[key]
                break
        if not matched_finance:
            for k, v in finance_dict.items():
                if k.startswith(b_clean_name):
                    matched_finance = v
                    break
        if not matched_finance:
            matched_finance = {'area': 0, 'rent': 0, 'comm_share': 0, 'threshold': 0, 'resource_pos': '无',
                               'open_date': ''}

        b['area'] = matched_finance['area']
        b['base_rent'] = matched_finance['rent']
        b['comm_share'] = matched_finance['comm_share']
        b['threshold'] = matched_finance['threshold']
        b['resource_pos'] = matched_finance['resource_pos']
        b['open_date'] = matched_finance.get('open_date', '')

        b['is_new_store'] = False
        if b['open_date']:
            try:
                open_dt = datetime.strptime(b['open_date'], '%Y-%m-%d')
                current_dt = datetime(y, m, 15)
                days_open = (current_dt - open_dt).days
                if days_open < 90: b['is_new_store'] = True
            except Exception:
                pass

        b['est_eff'] = b['estimate'] / b['area'] if b['area'] > 0 else 0.0
        est_comm = max(0, b['estimate'] - b['threshold']) * (b['comm_share'] / 100) if b['threshold'] > 0 else b[
                                                                                                                   'estimate'] * (
                                                                                                                           b[
                                                                                                                               'comm_share'] / 100)
        b['est_rent'] = max(b['base_rent'], est_comm)
        b['est_comm'] = est_comm

    cat2_area_total = defaultdict(float)
    cat2_rev_total = defaultdict(float)
    for b in brands.values():
        cat2 = b['cat2'] or '其他'
        cat2_area_total[cat2] += b.get('area', 0)
        cat2_rev_total[cat2] += b['estimate']
    cat2_eff_avg = {}
    for cat2 in cat2_area_total:
        cat2_eff_avg[cat2] = cat2_rev_total[cat2] / cat2_area_total[cat2] if cat2_area_total[cat2] > 0 else 0

    rt_brands = []
    for name, b in d_cur['brand_day'].items():
        active_days = len([v for v in b['days'].values() if v > 0])
        cur_floors = list(b['floors_set'])
        cur_floor_str = "、".join(cur_floors)
        brand_info = brands.get(name, {})
        prev_floors = list(brand_info.get('prev_floors', []))

        moved_flag = ""
        if len(cur_floors) > 1 or len(prev_floors) > 1:
            moved_flag = f"🏪一牌多铺(本月:{cur_floor_str})"
        elif cur_floors and prev_floors and cur_floors[0] not in prev_floors:
            moved_flag = f"🚨发生移位({prev_floors[0]}→{cur_floors[0]})"

        pv = sum(
            d_prev['brand_day'].get(name, {}).get('days', {}).get(f'{args.prev_ym[0]}-{args.prev_ym[1]:02d}-{d:02d}', 0)
            for d in cur_days)
        yv = sum(
            d_yoy['brand_day'].get(name, {}).get('days', {}).get(f'{args.yoy_ym[0]}-{args.yoy_ym[1]:02d}-{d:02d}', 0)
            for d in cur_days)

        rt_brands.append({
            'name': name, 'cat1': b['cat1'], 'cat2': b['cat2'], 'floor': cur_floor_str,
            'cur': b['total'], 'prev': pv, 'yoy': yv, 'active_days': active_days, 'total_days': actual_cnt,
            'moved_flag': moved_flag,
            'mom': (b['total'] / pv - 1) * 100 if pv > 0 else None,
            'rt_yoy': (b['total'] / yv - 1) * 100 if yv > 0 else None
        })
    rt_brands.sort(key=lambda x: x['cur'], reverse=True)

    prev_c1, prev_c2, _ = cat_totals(args.prev_file, args.project)
    yoy_c1, yoy_c2, _ = cat_totals(args.yoy_file, args.project)
    c1, c2 = defaultdict(lambda: {'tr': 0, 'prev': 0, 'y25': 0, 'n': 0}), defaultdict(
        lambda: {'tr': 0, 'prev': 0, 'y25': 0, 'n': 0, 'c1': ''})
    for b in brands.values():
        k1, k2 = b['cat1'] or '其他', b['cat2'] or '其他'
        for d, k in ((c1, k1), (c2, k2)):
            d[k]['tr'] += b['estimate']
            d[k]['n'] += 1
        c1[k1]['prev'] = prev_c1.get(k1, 0.0);
        c1[k1]['y25'] = yoy_c1.get(k1, 0.0)
        c2[k2]['c1'] = k1;
        c2[k2]['prev'] = prev_c2.get(k2, 0.0);
        c2[k2]['y25'] = yoy_c2.get(k2, 0.0)

    comm_map = load_comm_map(args.comm_file)
    total_comm, comm_detail, comm_excluded = 0.0, [], 0
    for n, b in brands.items():
        if b['name'] in EXCLUDE_COMM_BRANDS or b['cat2'] in EXCLUDE_COMM_CAT2:
            b['rate'] = b['threshold'] = b['comm'] = 0.0;
            b['comm_excluded'] = True;
            comm_excluded += 1
            continue
        c = comm_map.get(n, {'rate': 0.0, 'threshold': 0.0})
        if c['rate'] == 0:
            for k, v in comm_map.items():
                if n in k or k in n: c = v; break
        b['rate'], b['threshold'], b['comm_excluded'] = c['rate'], c['threshold'], False
        b['comm'] = 0.0
        if c['rate'] > 0:
            if c['threshold'] > 0:
                b['comm'] = max(0.0, b['estimate'] - c['threshold'] * 10000) * c['rate'] / 100
            else:
                b['comm'] = b['estimate'] * c['rate'] / 100
        total_comm += b['comm']
        if b['comm'] > 0: comm_detail.append(b)
    comm_detail.sort(key=lambda x: x['comm'], reverse=True)
    comm_hit = sum(1 for b in comm_detail if b['estimate'] >= b['threshold'] * 10000)

    inc_rows, inc_total, inc_gap = [], 0.0, max(0.0, gap)
    if args.increment and os.path.exists(args.increment):
        with open(args.increment, 'r', encoding='utf-8') as fh:
            plan = json.load(fh)
        alloc = 0.0;
        proc = []
        for e in plan:
            tr = sum(brands.get(n, {}).get('estimate', 0.0) for n in e['brands'])
            if 'target' in e:
                inc = e['target'] - tr
            else:
                inc = e.get('increment', 0) or 0
            is_rem = 'remainder' in e
            if not is_rem and inc > 0: alloc += inc
            proc.append({**e, 'tr': tr, 'inc': inc, '_rem': is_rem})
        for p in proc:
            if p['_rem']: p['inc'] = max(0.0, inc_gap - alloc)
        for p in proc:
            for n in p['brands']:
                b = brands.get(n)
                if not b or p['inc'] <= 0: continue
                s = b['estimate'] / p['tr'] if p['tr'] > 0 else 1 / len(p['brands'])
                inc_rows.append({'nm': n, 'c1': b['cat1'], 'c2': b['cat2'], 'ty': p.get('type', ''),
                                 'tr': b['estimate'], 'inc': p['inc'] * s,
                                 'adj': b['estimate'] + p['inc'] * s, 'y25': b['yoy_actual']})
        inc_rows.sort(key=lambda x: x['inc'], reverse=True)
        inc_total = sum(r['inc'] for r in inc_rows)

    prev_full, yoy_full = d_prev['total'], d_yoy['total']
    mom_pct = (total_est / prev_full - 1) * 100 if prev_full > 0 else 0.0
    yoy_pct = (total_est / yoy_full - 1) * 100 if yoy_full > 0 else 0.0
    comp = [b for b in brands.values() if b['prev_actual'] > 0 and b['yoy_actual'] > 0]
    comp_est = sum(b['estimate'] for b in comp)
    comp_yoy = (comp_est / sum(b['yoy_actual'] for b in comp) - 1) * 100 if comp and sum(
        b['yoy_actual'] for b in comp) > 0 else 0.0
    comp_mom = (comp_est / sum(b['prev_actual'] for b in comp) - 1) * 100 if comp and sum(
        b['prev_actual'] for b in comp) > 0 else 0.0

    return dict(y=y, m=m, ndays=ndays, actual_total=actual_total, actual_cnt=actual_cnt,
                last_day=max(cur_days) if cur_days else 0,
                total_est=total_est, remaining=remaining, rem_wd=rem_wd, rem_we=rem_we,
                exclude_sum=exclude_sum, boost_extra=boost_extra, boost_info=boost_info,
                est_daily=est_daily, cur_dow=cur_dow, cal_days=cal_days,
                brands=brands, rt_brands=rt_brands, c1=c1, c2=c2,
                comm_map=comm_map, total_comm=total_comm, comm_detail=comm_detail,
                comm_hit=comm_hit, comm_excluded=comm_excluded,
                target=target, gap=gap, rt_mom=rt_mom, rt_yoy=rt_yoy, prev_sp=prev_sp, yoy_sp=yoy_sp,
                prev_full=prev_full, yoy_full=yoy_full, mom_pct=mom_pct, yoy_pct=yoy_pct,
                comp=comp, comp_est=comp_est, comp_yoy=comp_yoy, comp_mom=comp_mom,
                inc_rows=inc_rows, inc_total=inc_total, scale=scale, exclude=exclude, cat2_eff_avg=cat2_eff_avg)


# ============================ HTML 渲染区 ============================
# (由于篇幅限制，这里保持你原来的 render_html 等函数不变，直接接上即可)
# ...

def get_core_summary_for_ai(r):
    problem_brands = []
    for b in r['rt_brands']:
        brand_detail = r['brands'].get(b['name'], {})
        area = brand_detail.get('area', 0)
        est_eff = brand_detail.get('est_eff', 0)
        est_rent = brand_detail.get('est_rent', 0)
        cat2_avg = r.get('cat2_eff_avg', {}).get(b['cat2'], 0)
        is_new = brand_detail.get('is_new_store', False)

        rt_yoy = b['rt_yoy'] if b['rt_yoy'] is not None else None
        rt_mom = b['mom'] if b['mom'] is not None else 0

        mom_str = f"{rt_mom:.1f}%"
        yoy_str = f"{rt_yoy:.1f}%" if rt_yoy is not None else "无基数"

        is_abnormal = False
        abnormal_msg = ""
        if b['cur'] < 5000 and b['cur'] > 0:
            if b['active_days'] < b['total_days'] / 2:
                is_abnormal = True
                abnormal_msg = "【疑似停业/断网】"
            else:
                is_abnormal = True
                abnormal_msg = "【疑似流水异常漏报】"

        is_warning = False
        if rt_yoy is not None and rt_yoy < -5:
            is_warning = True
        elif rt_yoy is None and rt_mom < -5:
            is_warning = True
        elif cat2_avg > 0 and est_eff < cat2_avg * 0.5 and b['cur'] > 0:
            is_warning = True

        if is_warning and b['cur'] > 0:
            if (rt_yoy is not None and rt_yoy < -50) or (rt_yoy is None and rt_mom < -50):
                cliff_msg = "🔴断崖"
            else:
                cliff_msg = "🟠下滑"

            problem_brands.append({
                "品牌": b['name'], "业态": b['cat2'], "本月实际": b['cur'],
                "环比": mom_str, "同比": yoy_str,
                "面积": area, "预估坪效": est_eff, "行业均值": cat2_avg, "预估租金": est_rent,
                "出单天数": f"{b['active_days']}/{b['total_days']}天",
                "移位标记": b.get('moved_flag', ''),
                "新店标记": "🆕新店" if is_new else "",
                "异常特征": f"{abnormal_msg}{cliff_msg}"
            })

    problem_brands.sort(key=lambda x: float(x["同比"].replace('无基数', '0').replace('%', '')))
    top_problems = problem_brands[:30]
    target_brands = [pb['品牌'] for pb in problem_brands[:5]]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    trend_text = get_12month_trend(base_dir, r['y'], r['m'], target_brands)

    summary = f"""
    【当前分析月份】：{r['y']}年{r['m']}月
    【⚠️ 异常大跌品牌明细（含业财坪效与出单天数）】：
    （注意：必须交叉验证！如果出单天数极少，说明可能重装停业；如果满勤但坪效极低，才是真正的吸血占地！带有“移位”标记的品牌，数据失效；带有“🆕新店”标记的，严禁使用同比考核！）

    | 品牌 | 业态 | 本月实际 | 环比 | 同比 | 面积(㎡) | 出单天数 | 单店预估坪效 | 业态平均坪效 | 预估租金 | 状态标签 |
    |---|---|---|---|---|---|---|---|---|---|---|
    """
    for pb in top_problems:
        summary += f"| {pb['品牌']} | {pb['业态']} | {pb['本月实际']:,.0f} | {pb['环比']} | {pb['同比']} | {pb['面积']:.1f} | **{pb['出单天数']}** | {pb['预估坪效']:,.1f} | **{pb['行业均值']:,.1f}** | {pb['预估租金']:,.0f} | **{pb['移位标记']}{pb['新店标记']}{pb['异常特征']}** |\n"

    summary += f"\n{trend_text}"
    return summary


def get_12month_trend(base_dir, current_year, current_month, target_brands):
    # ... 保持不变 ...
    trend_data = {brand: {} for brand in target_brands}
    curr_y, curr_m = current_year, current_month
    for _ in range(12):
        file_path = os.path.join(base_dir, "data_storage", f"{curr_y}年{curr_m}月.xlsx")
        if os.path.exists(file_path):
            try:
                df = pd.read_excel(file_path, header=None, skiprows=1)
                for _, r in df.iterrows():
                    name = str(r[COL_BRAND]).strip()
                    if name in target_brands:
                        val = pd.to_numeric(r[COL_AMT], errors='coerce')
                        if pd.notna(val) and val > 0:
                            month_str = f"{curr_y}-{curr_m:02d}"
                            trend_data[name][month_str] = trend_data[name].get(month_str, 0) + val
            except Exception:
                pass
        curr_m -= 1
        if curr_m == 0: curr_m = 12; curr_y -= 1

    result = "【重点品牌过去12个月营业额趋势（万元）】\n"
    for brand, data in trend_data.items():
        if not data: continue
        sorted_months = sorted(data.keys())
        trend_list = [f"{m}: {data[m] / 10000:.1f}万" for m in sorted_months]
        if trend_list: result += f"- {brand}：{', '.join(trend_list)}\n"
    return result


# ============================ HTML 渲染区 ============================
CSS = """
:root{--bg:#f1f5f9;--card:#fff;--t1:#1e293b;--t2:#475569;--t3:#64748b;--border:#e2e8f0;--blue:#2563eb;--green:#059669;--red:#dc2626;--orange:#d97706;--purple:#7c3aed;--pink:#db2777}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Microsoft YaHei',sans-serif;background:var(--bg);color:var(--t1);min-height:100vh}
.header{background:linear-gradient(135deg,#1e40af,#3b82f6);padding:24px 32px;box-shadow:0 4px 12px rgba(0,0,0,.12)}
.header h1{font-size:22px;font-weight:700;color:#fff}.header p{font-size:13px;color:rgba(255,255,255,.75);margin-top:4px}
.container{max-width:1500px;margin:0 auto;padding:20px 24px}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:24px}
.kpi-card{background:var(--card);border-radius:10px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.08);border:1px solid var(--border)}
.kpi-card.bl{border-left:4px solid var(--blue)}.kpi-card.gl{border-left:4px solid var(--green)}
.kpi-card.or{border-left:4px solid var(--orange)}.kpi-card.pu{border-left:4px solid var(--purple)}
.kpi-card.rd{border-left:4px solid var(--red)}.kpi-card.cy{border-left:4px solid #0891b2}.kpi-card.pk{border-left:4px solid var(--pink)}
.kpi-label{font-size:11px;color:var(--t3);margin-bottom:6px;font-weight:600;letter-spacing:.5px}
.kpi-value{font-size:23px;font-weight:700}.kpi-sub{font-size:11px;color:var(--t3);margin-top:2px}
.section-title{font-size:18px;font-weight:700;margin:28px 0 16px;padding-bottom:10px;border-bottom:2px solid var(--border);display:flex;align-items:center;gap:10px}
.section-title .icon{width:6px;height:24px;background:var(--blue);border-radius:3px}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;font-size:12px}
.legend span{display:inline-flex;align-items:center;gap:6px}.legend .dot{width:12px;height:12px;border-radius:3px}
.note{background:linear-gradient(135deg,#eff6ff,#dbeafe);border:1px solid #93c5fd;border-radius:10px;padding:14px 18px;margin-bottom:20px;font-size:13px;line-height:1.8}
.note.warn{background:linear-gradient(135deg,#fef2f2,#fee2e2);border-color:#fca5a5}
.note.promo{background:linear-gradient(135deg,#fdf2f8,#fce7f3);border-color:#f9a8d4}
.calendar{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;background:var(--card);border-radius:12px;padding:10px;box-shadow:0 1px 3px rgba(0,0,0,.08);border:1px solid var(--border)}
.cal-header{text-align:center;font-weight:700;font-size:12px;color:var(--t3);padding:6px 0}
.cal-cell{background:#f8fafc;border-radius:8px;padding:6px;text-align:center;min-height:66px;display:flex;flex-direction:column;align-items:center;justify-content:center;border:1px solid transparent;transition:.15s}
.cal-cell:hover{transform:translateY(-1px);box-shadow:0 2px 8px rgba(0,0,0,.1)}.cal-cell.empty{background:transparent;pointer-events:none}
.cal-day{font-size:13px;font-weight:700}.cal-dow{font-size:10px;color:var(--t3)}.cal-amt{font-size:11px;font-weight:700;margin-top:2px}
.cal-tag{font-size:9px;padding:1px 5px;border-radius:3px;margin-top:2px;font-weight:600}
.cal-cell.actual{background:#f0fdf4;border-color:#bbf7d0}.cal-cell.actual .cal-amt{color:var(--green)}
.cal-cell.excluded{background:#fef2f2!important;border-color:#fca5a5!important}.cal-cell.excluded .cal-amt{color:#dc2626!important}
.cal-cell.boost{background:#fdf2f8!important;border-color:#f9a8d4!important}.cal-cell.boost .cal-amt{color:var(--pink)!important}
.cal-cell.forecast{background:#fefce8;border-color:#fef08a}.cal-cell.forecast .cal-amt{color:var(--orange)}
.filter-bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px;padding:14px 16px;background:var(--card);border-radius:10px;border:1px solid var(--border);box-shadow:0 1px 3px rgba(0,0,0,.05)}
.filter-bar label{font-size:12px;font-weight:600;color:var(--t2);white-space:nowrap}
.filter-bar select{padding:5px 28px 5px 10px;border:1px solid var(--border);border-radius:6px;font-size:12px;background:#fff;color:var(--t1);appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 8px center;cursor:pointer}
.filter-bar select:focus{outline:none;border-color:var(--blue);box-shadow:0 0 0 2px rgba(37,99,235,.15)}
.filter-info{font-size:12px;color:var(--t3);margin-left:auto}.filter-info strong{color:var(--t1)}
.filter-sort{display:flex;gap:6px;margin-left:8px}
.filter-sort button{padding:3px 10px;border:1px solid var(--border);border-radius:5px;background:#fff;font-size:11px;cursor:pointer;color:var(--t2);white-space:nowrap}
.filter-sort button:hover{background:#f1f5f9}
.filter-sort button.active{background:var(--blue);color:#fff;border-color:var(--blue);font-weight:600}
.table-wrap{overflow-x:auto;background:var(--card);border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);border:1px solid var(--border);max-height:70vh;overflow-y:auto}
.table-wrap.no-scroll{max-height:none;overflow-y:visible}
table{width:100%;border-collapse:collapse;font-size:13px}thead{position:sticky;top:0;z-index:2}
th{background:#f8fafc;padding:10px 8px;text-align:left;font-weight:700;font-size:11px;color:var(--t3);border-bottom:2px solid var(--border);white-space:nowrap}
th.num{text-align:right}td{padding:8px;border-bottom:1px solid #f1f5f9}td.num{text-align:right;font-variant-numeric:tabular-nums}td.strong{font-weight:700;color:var(--blue)}
tr:hover td{background:#f8fafc}tr.filtered{display:none}
.increment-section{background:linear-gradient(135deg,#f0fdf4,#ecfdf5);border:2px solid #86efac;border-radius:12px;padding:20px 24px;margin-bottom:24px}
.increment-section h3{color:var(--green);font-size:16px;margin-bottom:12px}
.increment-section .summary{font-size:13px;margin-bottom:16px;line-height:1.8}
.gap-highlight{background:#fef2f2;color:#dc2626;font-weight:700;padding:2px 6px;border-radius:4px}
.gap-fill{background:#f0fdf4;color:#059669;font-weight:700;padding:2px 6px;border-radius:4px}
@media(max-width:768px){.calendar{grid-template-columns:repeat(7,1fr);gap:3px;padding:6px}.cal-cell{padding:3px 2px 5px;min-height:48px}.cal-amt{font-size:9px}.filter-bar{flex-direction:column;align-items:stretch}}
"""

JS = """
(function(){
function setupFilter(tbId,rowCountId,cat1Id,cat2Id,floorId,btnSel,sortSel){
  var tb=document.getElementById(tbId).querySelector('tbody');
  var rs=Array.from(tb.querySelectorAll('tr'));
  var c1s=new Set(),c2s=new Set(),fs=new Set();
  rs.forEach(function(r){c1s.add(r.dataset.c1);c2s.add(r.dataset.c2);fs.add(r.dataset.fl)});
  function fi(id,v){var s=document.getElementById(id);if(!s)return;s.innerHTML='<option value="">全部</option>';Array.from(v).sort().forEach(function(x){if(!x)return;var o=document.createElement('option');o.value=x;o.textContent=x;s.appendChild(o)})}
  fi(cat1Id,c1s);fi(cat2Id,c2s);fi(floorId,fs);
  function applyFilters(){
    var c1v=document.getElementById(cat1Id).value,c2v=(cat2Id&&document.getElementById(cat2Id)?document.getElementById(cat2Id).value:''),f=document.getElementById(floorId).value,n=0;
    rs.forEach(function(r){var sh=(!c1v||r.dataset.c1===c1v)&&(!c2v||r.dataset.c2===c2v)&&(!f||r.dataset.fl===f);r.classList.toggle('filtered',!sh);if(sh)n++});
    document.getElementById(rowCountId).textContent=n;
  }
  function sortTable(k){
    var rows=Array.from(tb.querySelectorAll('tr'));
    rows.sort(function(a,b){
      var va=parseFloat(a.dataset.aug),vb=parseFloat(b.dataset.aug);
      var ma=parseFloat(a.dataset.mom),mb=parseFloat(b.dataset.mom);
      var ya=parseFloat(a.dataset.yoy),yb=parseFloat(b.dataset.yoy);
      if(k.indexOf('desc')>0&&k.indexOf('mom')<0&&k.indexOf('yoy')<0) return vb-va;
      if(k==='mom_asc') return mb-ma;
      if(k==='mom_desc') return ma-mb;
      if(k==='yoy_asc') return yb-ya;
      if(k==='yoy_desc') return ya-yb;
      return vb-va;
    });
    rows.forEach(function(r){tb.appendChild(r)});
    applyFilters();
  }
  var btns=document.querySelectorAll(btnSel);
  btns.forEach(function(b){
    b.addEventListener('click',function(){
      btns.forEach(function(x){x.classList.remove('active')});
      this.classList.add('active');
      sortTable(this.dataset.sort);
    });
  });
  [cat1Id,cat2Id,floorId].forEach(function(id){var e=document.getElementById(id);if(e)e.addEventListener('change',applyFilters)});
  sortTable(sortSel);
}
setupFilter('brandTable','rowCount','brandC1','brandC2','brandFloor','#brandSort button','aug_desc');
setupFilter('rtTable','rtRowCount','rtC1','rtC2','rtFloor','#rtSort button','aug_desc');
})();
(function(){
var t2=document.getElementById('cat2Table');if(!t2)return;
var r2=Array.from(t2.querySelector('tbody').querySelectorAll('tr'));
var cc1=new Set();r2.forEach(function(r){cc1.add(r.dataset.c1)});
var s2=document.getElementById('c2FilterC1');
Array.from(cc1).sort().forEach(function(x){var o=document.createElement('option');o.value=x;o.textContent=x;s2.appendChild(o)});
function f2(){var v=s2.value,n=0;r2.forEach(function(r){var sh=!v||r.dataset.c1===v;r.classList.toggle('filtered',!sh);if(sh)n++});document.getElementById('c2RowCount').textContent=n}
s2.addEventListener('change',f2);f2();
})();
"""

def fmt_money(v, dec=2):
    return '--' if not v or v <= 0 else f'{v/10000:.{dec}f}万'

def fmt_pct(a, b):
    if not b or b <= 0:
        return '--'
    p = (a / b - 1) * 100
    c = 'green' if p >= 0 else 'red'
    return f'<span style="color:var(--{c})">{p:+.1f}%</span>'

def fmt_pct_v(p):
    if p is None:
        return '--'
    c = 'green' if p >= 0 else 'red'
    return f'<span style="color:var(--{c})">{p:+.1f}%</span>'

def render_html(r, args):
    y, m = r['y'], r['m']
    prev_label = f'{args.prev_ym[0]}-{args.prev_ym[1]:02d}'
    yoy_label = f'{args.yoy_ym[0]}-{args.yoy_ym[1]:02d}'
    P = []
    P.append(f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
             f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
             f'<title>{y}年{m}月 全月业绩预测报告（去车营业额）</title><style>{CSS}</style></head><body>')
    sub = f'数据截至 {m}/{r["actual_cnt"]} · O列去车销售额口径'
    if r['target'] > 0:
        sub += f' · 目标 {r["target"]/10000:.0f}万'
    P.append(f'<div class="header"><h1>{y}年{m}月 全月业绩预测报告（去车营业额）</h1>'
             f'<p>{sub} · 生成: {datetime.now():%Y-%m-%d}</p></div><div class="container">')

    # KPI
    gap_cls, gap_txt = ('rd', '低于目标') if r['gap'] > 0 else ('gl', '高于目标')
    P.append('<div class="kpi-grid">')
    P.append(f'<div class="kpi-card gl"><div class="kpi-label">{m}/1-{r["actual_cnt"]} 实际</div>'
             f'<div class="kpi-value" style="color:var(--green)">{fmt_money(r["actual_total"])}</div>'
             f'<div class="kpi-sub">{r["actual_cnt"]}天 · 日均 {r["actual_total"]/max(1,r["actual_cnt"])/10000:.1f}万</div></div>')
    if r['exclude_sum'] > 0:
        ex = ','.join(sorted(d[-5:] for d in r['exclude']))
        P.append(f'<div class="kpi-card rd"><div class="kpi-label">剔除日({ex})</div>'
                 f'<div class="kpi-value" style="color:var(--red)">{fmt_money(r["exclude_sum"])}</div>'
                 f'<div class="kpi-sub">计入实际 · 不计入星期均值</div></div>')
    P.append(f'<div class="kpi-card cy"><div class="kpi-label">实时环比</div>'
             f'<div class="kpi-value" style="color:var(--{"green" if r["rt_mom"]>=0 else "red"})">{r["rt_mom"]:+.1f}%</div>'
             f'<div class="kpi-sub">vs {prev_label}同期 {fmt_money(r["prev_sp"])}</div></div>')
    P.append(f'<div class="kpi-card pu"><div class="kpi-label">实时同比</div>'
             f'<div class="kpi-value" style="color:var(--{"green" if r["rt_yoy"]>=0 else "red"})">{r["rt_yoy"]:+.1f}%</div>'
             f'<div class="kpi-sub">vs {yoy_label}同期 {fmt_money(r["yoy_sp"])}</div></div>')
    if len(r['boost_info']) and r['boost_extra']:
        bi = r['boost_info'][0]
        P.append(f'<div class="kpi-card pk"><div class="kpi-label">{args.boost_name or "促销日"} {bi["date"][-5:]}</div>'
                 f'<div class="kpi-value" style="color:var(--pink)">+{r["boost_extra"]/10000:.1f}万</div>'
                 f'<div class="kpi-sub">参考{bi["fest"]}较{bi["base"]} {(bi["ratio"]-1)*100:+.0f}%</div></div>')
    P.append(f'<div class="kpi-card or"><div class="kpi-label">{m}/{r["actual_cnt"]+1}-{r["ndays"]} 预测</div>'
             f'<div class="kpi-value" style="color:var(--orange)">{fmt_money(r["remaining"])}</div>'
             f'<div class="kpi-sub">{r["rem_wd"]}工作日+{r["rem_we"]}周末</div></div>')
    P.append(f'<div class="kpi-card bl"><div class="kpi-label">全月趋势</div>'
             f'<div class="kpi-value">{r["total_est"]/10000:.1f}万</div>'
             f'<div class="kpi-sub">实际 + 预测</div></div>')
    if r['target'] > 0:
        P.append(f'<div class="kpi-card gl"><div class="kpi-label">全月目标</div>'
                 f'<div class="kpi-value" style="color:var(--green)">{r["target"]/10000:.1f}万</div>'
                 f'<div class="kpi-sub">日均 {r["target"]/r["ndays"]/10000:.1f}万</div></div>')
        P.append(f'<div class="kpi-card {gap_cls}"><div class="kpi-label">目标差值</div>'
                 f'<div class="kpi-value" style="color:var(--{"red" if r["gap"]>0 else "green"})">{r["gap"]/10000:+.1f}万</div>'
                 f'<div class="kpi-sub">{gap_txt}</div></div>')
    P.append(f'<div class="kpi-card bl"><div class="kpi-label">{prev_label} 全月</div>'
             f'<div class="kpi-value">{r["prev_full"]/10000:.1f}万</div>'
             f'<div class="kpi-sub">环比基数 · 全月环比 {r["mom_pct"]:+.1f}%</div></div>')
    P.append(f'<div class="kpi-card pu"><div class="kpi-label">{yoy_label} 全月</div>'
             f'<div class="kpi-value">{r["yoy_full"]/10000:.1f}万</div>'
             f'<div class="kpi-sub">同比基数 · 全月同比 {r["yoy_pct"]:+.1f}%</div></div>')
    if r['comm_map']:
        P.append(f'<div class="kpi-card gl"><div class="kpi-label">预估抽成</div>'
                 f'<div class="kpi-value">{r["total_comm"]/10000:.1f}万</div>'
                 f'<div class="kpi-sub">{r["comm_hit"]}/{len(r["comm_detail"])}达抽({r["comm_excluded"]}剔除)</div></div>')
    P.append(f'<div class="kpi-card bl"><div class="kpi-label">可比品牌({len(r["comp"])})</div>'
             f'<div class="kpi-value">{r["comp_est"]/10000:.1f}万</div>'
             f'<div class="kpi-sub">同比 {r["comp_yoy"]:+.1f}% · 环比 {r["comp_mom"]:+.1f}%</div></div>')
    P.append('</div>')

    # 方法说明
    dow_txt = ' | '.join(f'{DOW_CN[i]} {r["est_daily"][i]/10000:.1f}万'
                         f'({"当月" if r["cur_dow"]["cnts"][i] else prev_label})' for i in range(7))
    P.append('<div class="note"><strong>预测方法 & 数据口径</strong><ul>'
             f'<li><strong>口径：</strong>O列·去车销售额（剔除汽车销售额）；数据源 {os.path.basename(args.cur_file)}</li>'
             f'<li><strong>实际：</strong>{m}/1-{r["actual_cnt"]} 共 <strong>{fmt_money(r["actual_total"])}</strong>'
             f'（{r["actual_cnt"]}天），实时环比 <strong>{r["rt_mom"]:+.1f}%</strong> · 实时同比 <strong>{r["rt_yoy"]:+.1f}%</strong></li>'
             f'<li><strong>星期均值：</strong>{dow_txt}'
             + (f'；剔除日合计 {fmt_money(r["exclude_sum"])}' if r['exclude_sum'] else '') + '</li>'
             f'<li><strong>剩余预测：</strong>{r["rem_wd"]}工作日+{r["rem_we"]}周末'
             + (f'+{args.boost_name or "促销日"}' if r['boost_extra'] else '')
             + f' = <strong>{fmt_money(r["remaining"])}</strong>；全月趋势 <strong>{fmt_money(r["total_est"])}</strong></li>'
             f'<li><strong>品牌分配：</strong>按已实现营业额占比分摊剩余预测；当月无营业的品牌按上月占比分摊</li></ul></div>')

    # 日历
    P.append(f'<div class="section-title"><div class="icon"></div>{y}年{m}月 业绩日历（{r["total_est"]/10000:.1f}万）</div>')
    P.append(f'<div class="legend"><span><span class="dot" style="background:#bbf7d0"></span>实际</span>'
             + ('<span><span class="dot" style="background:#fca5a5"></span>剔除日</span>' if r['exclude'] else '')
             + ('<span><span class="dot" style="background:#f9a8d4"></span>' + (args.boost_name or '促销日') + '</span>' if r['boost_info'] else '')
             + f'<span><span class="dot" style="background:#fef08a"></span>预测({fmt_money(r["remaining"])})</span></div>')
    P.append('<div class="calendar">' + ''.join(f'<div class="cal-header">{h}</div>' for h in CAL_HEADERS))
    lead = (datetime(y, m, 1).weekday() + 1) % 7
    P.extend(['<div class="cal-cell empty"></div>'] * lead)
    for d in range(1, r['ndays'] + 1):
        c = r['cal_days'][d]
        cls = 'boost ' if c['is_boost'] else ('excluded ' if c['is_excluded'] else ('actual ' if c['is_actual'] else 'forecast '))
        tag = f'<div class="cal-tag">{args.boost_name or "促销"}</div>' if c['is_boost'] else ''
        P.append(f'<div class="cal-cell {cls}"><div class="cal-day">{d}</div>'
                 f'<div class="cal-dow">{DOW_CN[c["dow"]]}</div>'
                 f'<div class="cal-amt">{c["amt"]/10000:.1f}万</div>{tag}</div>')
    P.append('</div>')

    # 实时同环比
    P.append(f'<div class="section-title"><div class="icon"></div>实时同比/环比（截至 {m}/{r["last_day"]} · {len(r["rt_brands"])}品牌）</div>')
    P.append(f'''<div class="filter-bar">
<label>一级业态</label><select id="rtC1"><option value="">全部</option></select>
<label>二级业态</label><select id="rtC2"><option value="">全部</option></select>
<label>楼层</label><select id="rtFloor"><option value="">全部</option></select>
<div class="filter-sort" id="rtSort"><span style="font-size:11px;color:var(--t3);margin-right:4px">排序:</span>
<button data-sort="aug_desc" class="active">营业额</button><button data-sort="mom_asc">环比+</button>
<button data-sort="mom_desc">环比-</button><button data-sort="yoy_asc">同比+</button><button data-sort="yoy_desc">同比-</button></div>
<span class="filter-info">显示 <strong id="rtRowCount">0</strong> / 共 <strong>{len(r["rt_brands"])}</strong></span></div>
<div class="table-wrap"><table id="rtTable"><thead><tr>
<th>品牌</th><th>一级业态</th><th>二级业态</th><th>楼层</th>
<th class="num">{m}/1-{r["actual_cnt"]}</th><th class="num">{prev_label}同期</th><th class="num">环比</th>
<th class="num">{yoy_label}同期</th><th class="num">同比</th></tr></thead><tbody>''')
    for b in r['rt_brands']:
        P.append(f'<tr data-c1="{b["cat1"]}" data-c2="{b["cat2"]}" data-fl="{b["floor"]}" '
                 f'data-aug="{b["cur"]/10000:.1f}" data-mom="{b["mom"] if b["mom"] is not None else -9999}" '
                 f'data-yoy="{b["rt_yoy"] if b["rt_yoy"] is not None else -9999}">'
                 f'<td><strong>{b["name"]}</strong></td><td>{b["cat1"]}</td><td>{b["cat2"]}</td><td>{b["floor"]}</td>'
                 f'<td class="num" style="font-weight:700">{fmt_money(b["cur"])}</td>'
                 f'<td class="num">{fmt_money(b["prev"])}</td><td class="num">{fmt_pct_v(b["mom"])}</td>'
                 f'<td class="num">{fmt_money(b["yoy"])}</td><td class="num">{fmt_pct_v(b["rt_yoy"])}</td></tr>')
    P.append('</tbody></table></div>')

    def cat_table(data, key_name, with_c1=False):
        rows = ''
        for k, d in sorted(data.items(), key=lambda x: x[1]['tr'], reverse=True):
            head = f'<td>{d["c1"]}</td>' if with_c1 else ''
            rows += (f'<tr data-c1="{d.get("c1","")}">{head}<td><strong>{k}</strong></td>'
                     f'<td class="num">{d["n"]}</td><td class="num">{fmt_money(d["tr"])}</td>'
                     f'<td class="num">{fmt_money(d["prev"])}</td><td class="num">{fmt_pct(d["tr"],d["prev"])}</td>'
                     f'<td class="num">{fmt_money(d["y25"])}</td><td class="num">{fmt_pct(d["tr"],d["y25"])}</td></tr>')
        return rows

    n1 = sum(d['n'] for d in r['c1'].values())
    t1 = sum(d['tr'] for d in r['c1'].values())
    p1 = sum(d['prev'] for d in r['c1'].values())
    y1 = sum(d['y25'] for d in r['c1'].values())
    P.append(f'<div class="section-title"><div class="icon"></div>一级业态 · 全月趋势（含同比环比）</div>'
             f'<div class="table-wrap no-scroll"><table><thead><tr><th>一级业态</th><th class="num">品牌数</th>'
             f'<th class="num">全月趋势</th><th class="num">{prev_label}</th><th class="num">环比</th>'
             f'<th class="num">{yoy_label}</th><th class="num">同比</th></tr></thead><tbody>{cat_table(r["c1"], "一级业态")}'
             f'<tr style="background:#f8fafc;font-weight:700"><td>合计</td><td class="num">{n1}</td>'
             f'<td class="num">{fmt_money(t1)}</td><td class="num">{fmt_money(p1)}</td>'
             f'<td class="num">{fmt_pct(t1,p1)}</td><td class="num">{fmt_money(y1)}</td>'
             f'<td class="num">{fmt_pct(t1,y1)}</td></tr></tbody></table></div>')

    P.append(f'<div class="section-title"><div class="icon"></div>二级业态 · 全月趋势（含同比环比）</div>'
             f'<div class="filter-bar"><label>一级业态</label><select id="c2FilterC1"><option value="">全部</option></select>'
             f'<span class="filter-info">显示 <strong id="c2RowCount">0</strong> / 共 <strong>{len(r["c2"])}</strong> 二级业态</span></div>'
             f'<div class="table-wrap no-scroll"><table id="cat2Table"><thead><tr><th>一级业态</th><th>二级业态</th>'
             f'<th class="num">品牌数</th><th class="num">全月趋势</th><th class="num">{prev_label}</th>'
             f'<th class="num">环比</th><th class="num">{yoy_label}</th><th class="num">同比</th></tr>'
             f'<tbody>{cat_table(r["c2"], "二级业态", with_c1=True)}</tbody></table></div>')

    # 品牌明细
    nB = len(r['brands'])
    daily = args.daily_avg
    P.append(f'<div class="section-title"><div class="icon"></div>品牌明细（{nB}品牌 · 按全月趋势排序）</div>')
    P.append(f'''<div class="filter-bar">
    <label>一级业态</label><select id="brandC1"><option value="">全部</option></select>
    <label>二级业态</label><select id="brandC2"><option value="">全部</option></select>
    <label>楼层</label><select id="brandFloor"><option value="">全部</option></select>
    <div class="filter-sort" id="brandSort"><span style="font-size:11px;color:var(--t3);margin-right:4px">排序:</span>
    <button data-sort="aug_desc" class="active">趋势额</button><button data-sort="mom_asc">环比+</button>
    <button data-sort="mom_desc">环比-</button><button data-sort="yoy_asc">同比+</button><button data-sort="yoy_desc">同比-</button></div>
    <span class="filter-info">显示 <strong id="rowCount">0</strong> / 共 <strong>{nB}</strong></span></div>
    <div class="table-wrap"><table id="brandTable"><thead><tr>
    <th>品牌</th><th>一级业态</th><th>二级业态</th><th>楼层</th>
    <th class="num">面积(㎡)</th><th class="num">保底(万)</th><th class="num">门槛(万)</th><th class="num">预抽成(万)</th><th class="num" style="color:var(--purple)">预实收(万)</th>
    <th class="num">{prev_label}全月</th><th class="num" style="color:var(--blue)">{m}月实际</th>
    <th class="num">全月趋势</th>''' +
             ('<th class="num">临界点</th>' if r['comm_map'] else '') +
             ('<th class="num">工作日日均</th><th class="num">周末日均</th>' if daily else '') +
             f'<th class="num">环比</th><th class="num">{yoy_label}</th><th class="num">同比</th></tr></thead><tbody>''')
    for b in sorted(r['brands'].values(), key=lambda x: x['estimate'], reverse=True):
        mom = (b['estimate'] / b['prev_actual'] - 1) * 100 if b['prev_actual'] > 0 else -9999
        yoy = (b['estimate'] / b['yoy_actual'] - 1) * 100 if b['yoy_actual'] > 0 else -9999
        extra = ''
        if daily:
            ws = wc = es = ec = 0.0
            for ds, v in b.get('days', {}).items():
                i = datetime.strptime(ds, '%Y-%m-%d').weekday()
                if i < 5:
                    ws += v; wc += 1
                else:
                    es += v; ec += 1
            extra = (f'<td class="num">{fmt_money(ws / wc, 1) if wc else "--"}</td>'
                     f'<td class="num">{fmt_money(es / ec, 1) if ec else "--"}</td>')

        P.append(f'<tr data-c1="{b["cat1"]}" data-c2="{b["cat2"]}" data-fl="{b["floor"]}" '
                 f'data-aug="{b["estimate"] / 10000:.1f}" data-mom="{mom:.4f}" data-yoy="{yoy:.4f}">'
                 f'<td><strong>{b["name"]}</strong></td><td>{b["cat1"]}</td><td>{b["cat2"]}</td><td>{b["floor"]}</td>'
                 f'<td class="num">{b.get("area", 0):.1f}</td>'
                 f'<td class="num">{b.get("base_rent", 0) / 10000:.2f}</td>'
                 f'<td class="num">{b.get("threshold", 0) / 10000:.2f}</td>'
                 f'<td class="num">{b.get("est_comm", 0) / 10000:.2f}</td>'
                 f'<td class="num strong" style="color:var(--purple)">{b.get("est_rent", 0) / 10000:.2f}</td>'
                 f'<td class="num">{fmt_money(b["prev_actual"])}</td>'
                 f'<td class="num" style="color:var(--blue)">{fmt_money(b["cur_actual"])}</td>'
                 f'<td class="num strong">{fmt_money(b["estimate"])}</td>'
                 + (f'<td class="num">{b["threshold"]:.2f}万</td>' if r['comm_map'] and b.get('threshold', 0) > 0 else
                    ('<td class="num">--</td>' if r['comm_map'] else ''))
                 + extra +
                 f'<td class="num">{fmt_pct(b["estimate"], b["prev_actual"])}</td>'
                 f'<td class="num">{fmt_money(b["yoy_actual"])}</td>'
                 f'<td class="num">{fmt_pct(b["estimate"], b["yoy_actual"])}</td></tr>')
    P.append('</tbody></table></div>')

    # 抽成
    if r['comm_map']:
        P.append(f'<div class="section-title"><div class="icon"></div>抽成预估（{len(r["comm_detail"])}品牌 · {r["total_comm"]/10000:.1f}万 · {r["comm_excluded"]}剔除）</div>')
        P.append('<p style="font-size:12px;color:var(--t3);margin-bottom:8px">'
                 f'公式来源：{os.path.basename(args.comm_file)} · 剔除：{" / ".join(sorted(EXCLUDE_COMM_BRANDS))} + {" / ".join(sorted(EXCLUDE_COMM_CAT2))}</p>'
                 '<div class="table-wrap"><table><thead><tr><th>#</th><th>品牌</th><th>一级业态</th>'
                 '<th class="num">全月趋势</th><th class="num">临界点</th><th class="num">抽成率</th>'
                 '<th class="num">预估抽成</th></tr></thead><tbody>')
        for i, b in enumerate(r['comm_detail'][:60]):
            P.append(f'<tr><td>{i+1}</td><td>{b["name"]}</td><td>{b["cat1"]}</td>'
                     f'<td class="num">{b["estimate"]/10000:.1f}万</td><td class="num">{b["threshold"]:.2f}万</td>'
                     f'<td class="num">{b["rate"]:.1f}%</td><td class="num">{b["comm"]/10000:.2f}万</td></tr>')
        P.append('</tbody></table></div>')

    # 增长路径
    if r['inc_rows']:
        rows = ''
        for x in r['inc_rows']:
            rows += (f'<tr><td>{x["nm"]}</td><td>{x["c1"]}</td><td>{x["c2"]}</td><td>{x["ty"]}</td>'
                     f'<td class="num">{fmt_money(x["tr"])}</td>'
                     f'<td class="num" style="color:var(--green);font-weight:700">+{x["inc"]/10000:.2f}万</td>'
                     f'<td class="num strong">{fmt_money(x["adj"])}</td><td class="num">{fmt_money(x["y25"])}</td>'
                     f'<td class="num">{fmt_pct(x["adj"],x["y25"])}</td></tr>')
        grp = defaultdict(float)
        for x in r['inc_rows']:
            grp[x['ty']] += x['inc']
        li = ''.join(f'<li>{k}：<span class="gap-fill">+{v/10000:.2f}万</span></li>' for k, v in grp.items())
        P.append(f'''<div class="section-title"><div class="icon"></div>增长路径（{len(r["inc_rows"])}品牌）</div>
<div class="increment-section"><div class="summary">
<div>全月目标：<strong>{r["target"]/10000:.2f}万</strong>　|　趋势预测：{r["total_est"]/10000:.2f}万　|　
<span class="gap-highlight">需补增量：{r["gap"]/10000:.2f}万</span></div>
<div style="margin-top:8px"><strong>增量分配：</strong><ul style="margin:4px 0 0 18px">{li}</ul></div></div>
<div class="table-wrap" style="max-height:50vh"><table><thead><tr><th>品牌</th><th>一级业态</th><th>二级业态</th>
<th>分配类型</th><th class="num">趋势预测</th><th class="num">增量</th><th class="num">调整后</th>
<th class="num">{yoy_label}</th><th class="num">同比</th></tr></thead><tbody>{rows}</tbody></table></div></div>''')

    P.append(f'</div><script>{JS}</script></body></html>')
    return '\n'.join(P)