from func_lib import login, get_case_stats, get_case_details
from share_lib import (
	formatted, read_input, is_li_case, refined_situ_list, print_and_record)
from configs import default_dept, n_show_situ_items
from secret import username_default, password_default
import re
import sys

def check_layaway(situ_list):
	re_layaway_start = re.compile(r'CY5-011.*分期')
	re_layaway_end = re.compile(r'CY5-01\d限期履行')
	for situ in situ_list:
		command = situ['COMMAND']
		if re_layaway_end.search(command) is not None:
			return None
		elif re_layaway_start.search(command) is not None:
			return situ
	return None

def get_main_seqno(session, uid):
	stats = get_case_stats(session, uid=uid, dept=default_dept)
	if len(stats) == 0:
		return False, '義務人查無未結案件'
	pos_main_case = []
	for exec_t in [1, 3, 4]:
		for case in stats:
			if not is_li_case(case) and case['EXEC_CASE'] == exec_t:
				pos_main_case.append(
					(case['EXEC_YEAR'], exec_t, case['EXEC_SEQNO']))
				break
	situ_list_pool = []
	pure = True
	for _y, _t, _n in pos_main_case:
		situ_list_pool += get_case_details(
			session, exec_y=_y, exec_t=_t, exec_n=_n)['SITU_LIST']
	situ_list_pool = sorted(
		refined_situ_list(situ_list_pool),
		key=lambda situ: situ['DATE'], reverse=True)
	y, t, n = None, None, None
	for situ in situ_list_pool:
		if situ['MAIN_SEQNO'] is not '':
			y, t, n = map(int, situ['MAIN_SEQNO'].split('-'))
			break
	if (y, t, n) == (None, None, None):
		return False, '義務人查無本股非勞健保已執行案件'
	return True, (y, t, n)

if __name__ == '__main__':
	if len(sys.argv) != 4:
		print (
			'使用說明: python [本程式名稱] [輸入檔名 (.csv)]'
			' [輸出檔名 (.csv)] [紀錄檔名 (.csv)]')
		sys.exit(0)
	deep = int(input('案號輸入者要查本案號還是主案號？ (1/本案號 2/主案號) '))
	if deep not in [1, 2]:
		raise ValueError('輸入應為 1 或 2')
	session = login(username_default, password_default)
	f_out = open(sys.argv[2], 'w', encoding='utf-8-sig')
	f_err = open(sys.argv[3], 'w', encoding='utf-8-sig')
	print (','.join(['案號', '義務人', '狀態', '狀態日期']), file=f_out)
	print (','.join(['日期', '內文', '備註', '主案號']), file=f_out)
	input_list = read_input(sys.argv[1])
	for index, uid_or_seqno in enumerate(input_list):
		use_uid = type(uid_or_seqno) is str
		if use_uid is True:
			input_str = uid_or_seqno
		else:
			input_str = formatted('%03d,%02d,%08d', uid_or_seqno)
		print ('(%d/%d) %s 查詢中...' %
			(index + 1, len(input_list), input_str))
		if use_uid is False:
			# if deep == 2, use_uid will be reset as True
			y, t, n = uid_or_seqno
			if deep == 2:
				uid = get_case_stats(
					session, exec_y=y, exec_t=t, exec_n1=n)[0]['DUTY_IDNO']
				use_uid = True
		else:
			uid = uid_or_seqno
		if use_uid is True:
			success, seqno_or_msg = get_main_seqno(session, uid)
			if success is False:
				print_and_record (input_str + ',' + seqno_or_msg, file=f_err)
				continue
			else:
				y, t, n = seqno_or_msg
		try:
			stats = get_case_stats(
				session, exec_y=y, exec_t=t, exec_n1=n, noendbox=False)[0]
		except IndexError:
			print_and_record (
				'%s,查無案件明細' % formatted('%03d-%02d-%08d', (y, t, n)),
				file=f_err)
			continue
		details = get_case_details(session, exec_y=y, exec_t=t, exec_n=n)
		if details is None:
			print_and_record (
				'%s,請確認閱讀權限' % formatted('%03d-%02d-%08d', (y, t, n)),
				file=f_err)
			continue
		situ_list = refined_situ_list(details['SITU_LIST'])
		layaway = check_layaway(situ_list)
		date_sep = lambda s: tuple(map(int, [s[:3], s[3: 5], s[5:]]))
		# check whether it is ended
		if stats['FINISH_DATE'] != '':
			status = '已掛結'
			status_date = date_sep(stats['FINISH_DATE'])
		# check whether it is ending
		elif stats['END_DATE'] != '':
			status = '已報結'
			status_date = date_sep(stats['END_DATE'])
		elif layaway is not None:
			status = '分期中'
			status_date = layaway['DATE']
		else:
			status = ''
			status_date = None
		duty_name_str = stats['DUTY_NAME']
		if details['IS_WHOLLY_OWNED'] is True:
			duty_name_str = '(獨資) ' + duty_name_str
		if details['IS_PARTNERSHIP'] is True:
			duty_name_str = '(合夥) ' + duty_name_str
		print (','.join([
			formatted('%03d-%02d-%08d', (y, t, n)), duty_name_str,
			status, formatted('%03d/%02d/%02d', status_date)
			]), file=f_out)
		for situ in situ_list[: n_show_situ_items]:
			print (','.join([
				formatted('%03d/%02d/%02d', situ['DATE']),
				situ['COMMAND'], str(situ['COMMENT']).replace(',', '，'),
				situ['MAIN_SEQNO']]), file=f_out)
		print (',' * (n_show_situ_items - 1), file=f_out)
	f_out.close()
	f_err.close()
