import os
import time
import argparse

from SRunLite import SrunClient

def main(host,protcol,username,password,sleeptime,ssl_verify):
    if host is None:
        host = 'gw.buaa.edu.cn'
    else:
        host = host.strip()

    if protcol is None:
        protcol = 'https'

    if ssl_verify is None:
        ssl_verify = True
    else:
        ssl_verify = ssl_verify.lower() in ['true', 'yes', '1']

    srun=SrunClient(srun_host=host,protcol=protcol,verify=ssl_verify)

    if username is None:
        username = input('Username: ')

    if password is None:
        import getpass
        password = password = getpass.getpass('Password: ')

    if username is None or password is None or username == '' or password == '':
        raise Exception('SRUN_USERNAME or SRUN_PASSWORD not set')

    if sleeptime is None:
        sleeptime = 5
    else:
        sleeptime = int(sleeptime)
        if sleeptime < 1:
            sleeptime = 1
            print('SRUN_SLEEPTIME too small, set to 1')

    def logger(msg):
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        print(f'[Srun AutoLogin {time_str}] {msg}')

    while True:
        try:
            is_available, is_online, _ = srun.is_connected()
            if not is_available:
                logger('Login server not available')
            elif not is_online:
                logger('Not online, try to login')
                try:
                    for i in range(3):
                        result = srun.login(username, password)
                        if result == 'ok':
                            logger('Login success')
                            break
                        else:
                            if result != 'challenge_expire_error':
                                logger(f'Login failed: {result}')
                                break
                            else:
                                logger('Challenge expired, retry')
                except Exception as e:
                    logger(f'Login failed: {e}')
        except Exception as e:
            logger(f'Error: {e}')
        time.sleep(sleeptime)

if __name__ == '__main__':
    # 读取环境变量
    host = os.getenv('SRUN_HOST')
    protcol = os.getenv('SRUN_PROTOCOL')
    username = os.getenv('SRUN_USERNAME')
    password = os.getenv('SRUN_PASSWORD')
    sleeptime = os.getenv('SRUN_SLEEPTIME')
    ssl_verify = os.getenv('SRUN_SSL_VERIFY')

    args=argparse.ArgumentParser()
    args.add_argument('--host',default=None)
    args.add_argument('--protcol',default=None)
    args.add_argument('--username',default=None)
    args.add_argument('--password',default=None)
    args.add_argument('--sleeptime',default=None)
    args.add_argument('--ssl_verify',default=None)
    args=args.parse_args()

    if args.host is not None:
        host=args.host
    if args.protcol is not None:
        protcol=args.protcol
    if args.username is not None:
        username=args.username
    if args.password is not None:
        password=args.password
    if args.sleeptime is not None:
        sleeptime=args.sleeptime
    if args.ssl_verify is not None:
        ssl_verify=args.ssl_verify

    main(host,protcol,username,password,sleeptime,ssl_verify)