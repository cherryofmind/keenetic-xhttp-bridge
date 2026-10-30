# Полная установка: от своих серверов до домашней сети

Читайте по порядку. Эта инструкция объясняет ручную установку; для помощника
с доступом к терминалу те же этапы обязательны. [Готовый запрос нейросети](AI_INSTALL.md).

Опорная среда: Ubuntu 24.04 + systemd на обоих VPS, Xray **26.10.29**,
KeeneticOS **5.1.8**, Entware на USB EXT4, XKeen **2.1**, режим **Hybrid**.
Другие модели/версии сначала проверяйте, а не считайте совместимыми автоматически.
Команды ниже не следует целиком вставлять одним скриптом: после каждого этапа
есть проверка. Чистая установка опубликованного пакета ещё не испытана целиком.

## 1. Что строим и зачем

| Часть | Что делает | Что туда не нужно устанавливать |
| --- | --- | --- |
| Управляющий компьютер | Создаёт новые ключи и файлы, передаёт их по SSH/SFTP | Постоянный VPN-шлюз для дома |
| VPS в РФ, `entry` | Принимает XHTTP с обязательным VLESS Encryption и создаёт второе соединение | AntiZapret, nginx, панель подписок, DNAT |
| Иностранный VPS, `exit` | Принимает второе соединение REALITY и выпускает запросы в Интернет | Второй экземпляр AntiZapret для этой схемы |
| USB/Entware | Хранит Linux-пакеты и конфиги на роутере | Рабочие данные владельца, которые можно стереть при форматировании |
| Xray на Keenetic | Выбирает DIRECT либо VPN по правилам | Отдельный клиент на каждом домашнем устройстве |
| XKeen | Создаёт правила перехвата и запускает Xray | Новое подключение в списке OpenVPN роутера |
| Geodata | Обновляемые домены и сервисные подсети | Общий для всех пользователей секретный профиль |

РФ-узел — полноценный аутентифицированный прокси, а не пересылка исходных пакетов
на иностранный IP. Это меняет первое плечо соединения, но не гарантирует обход
любой фильтрации. Иностранный IP видят сайты, отправленные в VPN. Остальной трафик
идёт через провайдера. На телефоне отдельный полный профиль работает иначе:
его трафик по умолчанию отправляется через цепочку.

Нужны два доступных вам VPS, свободные TCP-порты и разрешение менять эти узлы.
Не покупайте серверы повторно, если подходящие уже есть. Входящий публичный IP
у домашнего роутера не нужен. Для опорного варианта домен и свой сертификат
тоже не нужны: имя REALITY — отдельный параметр второго плеча.

## 2. Какие значения свои, а какие создаются автоматически

| Поле | Что вписать / откуда взять |
| --- | --- |
| `entry.host` | Публичный IP или разрешаемое имя своего РФ VPS; не адрес иностранного выхода |
| `exit.host` | Публичный IP или разрешаемое имя своего иностранного VPS |
| `entry.port` | Свободный TCP-порт РФ, по умолчанию `8080` |
| `exit.port` | Свободный TCP-порт иностранного VPS, по умолчанию `55443` |
| `exit.server_name` | Доступное с иностранного VPS имя цели REALITY; пример `www.microsoft.com` нужно проверить |
| `entry.id`, `exit.id` | Два разных UUID, создаются `init`; руками придумывать не нужно |
| `entry.encryption` / `decryption` | Парные значения `xray vlessenc`, создаются `init`; `none` здесь запрещён |
| `entry.path` | Случайный путь XHTTP, создаётся `init`; должен совпадать у клиента и РФ-входа |
| `exit.private_key` / `public_key` | Пара `xray x25519`, создаётся `init`; private остаётся только у владельца и на выходе |
| `exit.short_id` | Создаётся `init`; не общий идентификатор из чужого примера |
| `router_mips_receive_buffer` | По умолчанию `false`; `--mips-router` только для соответствующей проверенной MIPS-платформы |
| `rollback.old_interface` | Фактический идентификатор прежнего OpenVPN, а не его отображаемое название |
| `rollback.dns_profile` | Реальный прежний DNS53-профиль нужного сегмента |
| `rollback.old_dns` / `new_dns` | Адреса до/после вашего перехода; это не универсальная рекомендация DNS |

`198.51.100.10` и `203.0.113.20` в примерах — учебные адреса. Все строки `YOUR_*`
ниже замените своими значениями. Не используйте демонстрационные адреса как рабочие.
`settings.example.json` — справочник полей, не готовый профиль.

Генератор этой версии допускает порты `1024..65535`. Примеры `8080`/`55443`
помогают не занимать HTTPS-порт существующего сайта; это не маскировка под
обычный HTTPS на 443. Xray 26.10.29 выдаёт предупреждения для некоторых целей
REALITY, включая имя из примера, и для не-443 порта выхода. Успешный `-test`
не отменяет этих предупреждений: выбор цели проверяйте отдельно, гарантий
незаметности у примера нет. Смена схемы на низкие порты потребует адаптации
ограничений генератора, а не простой подстановки `443` в этом руководстве.

## 3. Зафиксировать исходное состояние

1. В панели Keenetic скачайте текущую конфигурацию в закрытую папку компьютера.
   Отдельно экспортируйте прежний OpenVPN с сертификатами: running-config может
   не содержать встроенный профиль. Запишите интерфейс, маршруты и приоритеты.
2. Запишите DNS, назначенный каждому изменяемому сегменту, и наличие DoH/DoT,
   интернет-фильтра, IPv6 и отдельных DNS/VPN-профилей на устройствах.
3. Сохраните существующие конфиги Xray/XKeen, сервисы, исключения, crontab,
   правила firewall. Копии храните вне каталогов загрузки Xray и вне Git.
4. Убедитесь, что знаете способ вернуть старый VPN и добраться до панели локально.
   При удалённой работе сохраните независимый канал связи.

На каждом VPS выполните **до установки**, через SSH в своей сессии:

```sh
cat /etc/os-release
uname -m
free -m
df -h
ss -lntup
systemctl list-units --type=service --state=running
```

Ожидается известная архитектура, место на диске и свободный целевой порт.
Если установлен чужой Xray или сервер занят задачами, не заменяйте его бинарник,
unit и конфиги. Сначала согласуйте изоляцию или выберите свободный узел.
Не сбрасывайте firewall. SSH-ключи храните на своём компьютере; доступ по паролю
не отключайте как побочный эффект установки.

## 4. Получить пакет и Xray на управляющем компьютере

Скачайте **Source code** нужного релиза со [страницы выпусков](https://github.com/cherryofmind/keenetic-xhttp-bridge/releases)
и распакуйте. Либо клонируйте репозиторий и сохраните `git rev-parse HEAD` в отчёт.
Работайте из корня, где лежат `README.md` и `tools/`. Python нужен версии 3.10+.

Для генерации нужен исполняемый Xray для **вашего компьютера**, не бинарник роутера.
Официальный [релиз Xray v26.10.29](https://github.com/XTLS/Xray-core/releases/tag/v26.10.29):

| Среда | Архив |
| --- | --- |
| Windows x64 | `Xray-windows-64.zip` |
| Linux x86_64 | `Xray-linux-64.zip` |
| Linux aarch64 | `Xray-linux-arm64-v8a.zip` |

Проверьте SHA-256 по данным официального релиза перед запуском. Для остальных
архитектур выберите соответствующий архив у Xray, не запускайте бинарник x64.

**Windows PowerShell**, пример локальной подготовки Xray в новой папке:

```powershell
$ErrorActionPreference = 'Stop'
$taskXrayDir = Join-Path $env:LOCALAPPDATA 'keenetic-xhttp-xray-26.10.29'
if (Test-Path -LiteralPath $taskXrayDir) { throw 'Папка уже существует: проверьте её, не перезаписывайте' }
New-Item -ItemType Directory -Path $taskXrayDir | Out-Null
$taskZip = Join-Path $taskXrayDir 'Xray-windows-64.zip'
Invoke-WebRequest 'https://github.com/XTLS/Xray-core/releases/download/v26.10.29/Xray-windows-64.zip' -OutFile $taskZip
$taskExpected = 'fce33e81cccf50e7aab572b175519a50b5e0f9d2f5c8d1ed73012ea5c9ad4d58'
if ((Get-FileHash -LiteralPath $taskZip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskExpected) { throw 'SHA-256 mismatch' }
Expand-Archive -LiteralPath $taskZip -DestinationPath $taskXrayDir
$taskXray = Join-Path $taskXrayDir 'xray.exe'
& $taskXray version
python --version
```

Далее в PowerShell из корня распакованного проекта:

```powershell
python tools/render.py init --xray $taskXray --entry-host YOUR_RU_VPS --exit-host YOUR_FOREIGN_VPS
```

**Linux/macOS**, если подходящий официальный Xray уже распакован:

```sh
/ABSOLUTE/PATH/TO/xray version
python3 --version
umask 077
python3 tools/render.py init --xray /ABSOLUTE/PATH/TO/xray --entry-host YOUR_RU_VPS --exit-host YOUR_FOREIGN_VPS
```

На Linux Xray можно установить по следующему разделу и использовать установленный
путь. На macOS выбирайте официальный macOS-архив; серверная Linux-команда не подходит.

Ожидается только сообщение о записи локальных файлов. Появится `settings.local.json`.
Не показывайте его целиком в чат. В защищённом редакторе проверьте поля по таблице
раздела 2, при необходимости измените порты и `server_name` **до** render.

Для своих дополнений создайте `custom-domains.local.txt` и `custom-ips.local.txt`.
По одному домену без `https://`/пути или IP/CIDR на строку; пустой файл допустим.
Домен включает поддомены, комментарии начинаются с `#`. Дополнения из папки
`configs/` — только примеры. Выполните один вариант:

```sh
# Linux/macOS: python3; Windows PowerShell: python
python3 tools/render.py render
# Либо со своими обоими файлами вместо предыдущей команды:
# python3 tools/render.py render --domains custom-domains.local.txt --ips custom-ips.local.txt
```

Появится `generated/`. При повторной генерации используйте новый подкаталог,
например `--output generated/revision-2`; не удаляйте действующие секреты.
Сохраните settings и результат в закрытой резервной копии. На Windows проверьте
доступ к папке своего пользователя: Unix-права не заменяют NTFS ACL.

## 5. Xray на двух VPS

Этот блок — для **нового/выделенного Ubuntu VPS**, root shell. Если работаете
через обычного пользователя с sudo, сначала откройте `sudo -i`. Исполните на
обоих узлах; он откажется заменять существующий `/usr/local/bin/xray`.
Совместимый существующий бинарник можно сохранить, проверив его версию отдельно.

```sh
set -eu
test ! -e /usr/local/bin/xray || { echo 'Existing Xray: inspect owner and version first'; exit 1; }
apt-get update
apt-get install -y ca-certificates curl unzip
case "$(uname -m)" in
  x86_64) task_asset=Xray-linux-64.zip; task_sha=8a5f3e6a1057e4bd0f8a7c57c9d91204b4be0b74222a6e210d070603101163c2 ;;
  aarch64|arm64) task_asset=Xray-linux-arm64-v8a.zip; task_sha=afe01f19045b05237420328028ee1ee2e1edd2100eb41a8cbbf50e683b0a6e58 ;;
  *) echo 'Unsupported architecture in this recipe'; exit 1 ;;
esac
task_stage=$(mktemp -d /root/home-xray-install.XXXXXX)
chmod 700 "$task_stage"
curl -fL --retry 2 "https://github.com/XTLS/Xray-core/releases/download/v26.10.29/$task_asset" -o "$task_stage/$task_asset"
printf '%s  %s\n' "$task_sha" "$task_stage/$task_asset" | sha256sum -c -
unzip -q "$task_stage/$task_asset" -d "$task_stage/core"
install -m 755 "$task_stage/core/xray" /usr/local/bin/xray
/usr/local/bin/xray version
install -d -m 700 /etc/home-xray
```

Ожидается SHA-256 `OK` и Xray 26.10.29. Архив оставлен в закрытом временном
каталоге, без секретов. Бинарные GeoIP/GeoSite с VPS-архива этой серверной
конфигурации не требуются: выборочная маршрутизация выполняется на роутере.

С управляющего компьютера передайте **через SSH/SFTP** в закрытую временную папку
каждого сервера (здесь пример root SSH; пользователь/порт ваши):

| Сервер | Из проекта | Временное имя на сервере |
| --- | --- | --- |
| Иностранный | `generated/server/exit.json` | `/root/home-xray-upload/exit.json` |
| Иностранный | `systemd/home-xray-exit.service` | `/root/home-xray-upload/home-xray-exit.service` |
| РФ | `generated/server/entry.json` | `/root/home-xray-upload/entry.json` |
| РФ | `systemd/home-xray-entry.service` | `/root/home-xray-upload/home-xray-entry.service` |

Например, из **терминала компьютера**, не роутера и не одного VPS в другой:

```sh
ssh root@YOUR_FOREIGN_VPS 'umask 077; mkdir -p /root/home-xray-upload; chmod 700 /root/home-xray-upload'
scp generated/server/exit.json systemd/home-xray-exit.service root@YOUR_FOREIGN_VPS:/root/home-xray-upload/
ssh root@YOUR_RU_VPS 'umask 077; mkdir -p /root/home-xray-upload; chmod 700 /root/home-xray-upload'
scp generated/server/entry.json systemd/home-xray-entry.service root@YOUR_RU_VPS:/root/home-xray-upload/
```

При первом SSH-входе проверьте fingerprint по доверенному каналу панели хостера;
не отключайте known-hosts проверку. Если root SSH запрещён, передавайте файлы
в закрытый каталог своего пользователя, затем устанавливайте через sudo.

**Сначала иностранный сервер**, root shell:

```sh
set -eu
if [ -e /etc/home-xray/exit.json ] || systemctl cat home-xray-exit.service >/dev/null 2>&1; then
  echo 'Existing config or service: stop and inspect'; exit 1
fi
install -m 600 /root/home-xray-upload/exit.json /etc/home-xray/exit.json
/usr/local/bin/xray run -test -config /etc/home-xray/exit.json
install -m 644 /root/home-xray-upload/home-xray-exit.service /etc/systemd/system/home-xray-exit.service
systemctl daemon-reload
systemctl enable --now home-xray-exit.service
systemctl is-active home-xray-exit.service
ss -lntp
```

**Затем РФ-сервер**, root shell:

```sh
set -eu
if [ -e /etc/home-xray/entry.json ] || systemctl cat home-xray-entry.service >/dev/null 2>&1; then
  echo 'Existing config or service: stop and inspect'; exit 1
fi
install -m 600 /root/home-xray-upload/entry.json /etc/home-xray/entry.json
/usr/local/bin/xray run -test -config /etc/home-xray/entry.json
install -m 644 /root/home-xray-upload/home-xray-entry.service /etc/systemd/system/home-xray-entry.service
systemctl daemon-reload
systemctl enable --now home-xray-entry.service
systemctl is-active home-xray-entry.service
ss -lntp
```

Ожидаются `Configuration OK`, `active` и свои порты в `LISTEN`. При ошибке смотрите
`journalctl -u home-xray-entry.service -n 40 --no-pager` либо аналогичный exit-unit.
Чужие файлы/юниты не заменяйте: при их наличии остановитесь и разберите владельца.

В **облачном и системном** firewall разрешите TCP к entry-порту из нужных
клиентских сетей и TCP к exit-порту с РФ-узла. Если IPv4 выхода РФ при соединении
отличается от публичного адреса панели, сначала установите реальный источник.
При активном UFW пример добавочных правил на нужном узле:

```sh
# РФ: свой entry.port вместо 8080; all-sources нужен для мобильных клиентов.
ufw allow 8080/tcp
# Иностранный: свои адрес РФ и exit.port вместо примера.
ufw allow from YOUR_RU_PUBLIC_IPV4 to any port 55443 proto tcp
ufw status numbered
```

Не включайте UFW вслепую на удалённом узле, не удаляйте правила SSH и не делайте
`flush`. Для nftables/iptables/cloud security group создайте эквивалентное узкое
правило в уже используемой системе. Проверьте доступ к имени цели REALITY на 443
**с иностранного сервера**, например
`curl -I --connect-timeout 10 https://www.microsoft.com/` для имени из примера.
Это проверка достижимости цели, а совместимость REALITY подтверждает следующий этап.

## 6. Проверить цепочку до изменения домашней сети

В совместимый клиент импортируйте `generated/mobile/profile.txt` (VLESS URI),
при необходимости `generated/mobile/client.json`. Поддержка XHTTP **вместе** с
VLESS Encryption и Vision обязательна. Название «поддерживает VLESS» недостаточно.
Версию ядра и ограничения мобильного импорта смотрите в README/SETUP.

Без установки системного TUN можно запустить JSON на **компьютере** вторым
терминалом; он слушает только SOCKS loopback `10808`:

```sh
/ABSOLUTE/PATH/TO/xray run -test -config generated/mobile/client.json
/ABSOLUTE/PATH/TO/xray run -config generated/mobile/client.json
```

На Windows вместо пути используйте `& $taskXray run ...`. Предварительно проверьте,
что `10808` свободен. Пока процесс работает, в другом терминале выполните
(`curl.exe` в Windows, чтобы не вызвать псевдоним PowerShell):

```sh
curl --proxy socks5h://127.0.0.1:10808 --connect-timeout 10 --max-time 30 https://api.ipify.org
curl --proxy socks5h://127.0.0.1:10808 --connect-timeout 10 --max-time 30 -I https://example.com/
```

Ожидается фактический иностранный egress-IP (он может отличаться при NAT хостера)
и корректный ответ HTTPS. Это доказывает больше, чем один открытый порт, но ещё
не приёмка приложений. В обычном клиенте проверьте сайты, сообщение и видео.
Затем завершите только запущенный вами тестовый процесс через Ctrl+C.
Если цепочка не работает, домашний OpenVPN пока не трогайте.

## 7. Подготовить USB, Entware и доступ к роутеру

Если всё уже установлено, проверьте и пропустите подготовку вместо переустановки.
Если нет: сохраните данные USB, определите накопитель по модели/объёму и только
после разрешения на стирание отформатируйте **его** в EXT4 через панель роутера.
Для роутера нужны поддержка USB/EXT4, OPKG/Entware и Netfilter/TPROXY-компоненты.
Названия компонентов зависят от модели/прошивки. Установка компонентов может
потребовать обновления и reboot; заранее согласуйте окно.

В приложении OPKG выберите подготовленный накопитель и установите Entware
по [официальной инструкции](https://support.netcraze.ru/giga/nc-1012/ru/20980-installing-the-entware-repository-on-a-usb-drive.html).
Выберите в инструкции свою модель/архитектуру: ссылка открывает пример модели.
Не загружайте произвольный Entware-архив от другого процессора. Ожидаемый initrc
обычно `/opt/etc/init.d/rc.unslung`; проверьте по своей версии инструкции.

Подключитесь именно к **Entware shell**: Linux-команды ниже не выполняются в CLI
Keenetic. Порт Entware SSH может отличаться от 22. Установите свой пароль/ключ
по официальной инструкции; не оставляйте заводской пароль и не открывайте shell
на WAN. В shell роутера проверьте:

```sh
uname -m
mount
df -h /opt
free -m
command -v opkg
command -v xray
pidof xray
```

Нужно монтирование `/opt` на нужном USB и свободное место. Известный KN-1713 имеет
мало RAM: произвольный рост буферов и параллельные прокси могут привести к нехватке
памяти. Не добавляйте swap/GC-тюнинг вместо измерений как обязательный шаг.

## 8. Установить XKeen без запуска перехвата

При уже работающем XKeen/Xray сначала сохраните его настройки и разберите
конфликты. Следующий блок предназначен для новой Entware-установки. Официальный
[порядок установки XKeen](https://github.com/jameszeroX/XKeen/wiki/Порядок-установки)
нужно сверить с текущей версией. KeeneticOS 5.2 требует дополнительного RCI-токена;
это отличается от опорной 5.1.8 — настройте токен по upstream и проверьте доступ
до продолжения. Не публикуйте токен.

**Entware shell роутера**:

```sh
opkg update
opkg install curl tar jq
cd /tmp
curl -fL https://raw.githubusercontent.com/jameszeroX/XKeen/1c1a9c719c16950f2ee657eef88d23021719facb/install.sh -o home-xkeen-install.sh
sh -n home-xkeen-install.sh
# Прочитайте загруженный сценарий до исполнения.
sh home-xkeen-install.sh --legacy 2.1
```

Bootstrap зафиксирован commit, `--legacy 2.1` — имя параметра upstream для выбора
конкретного тега **2.1**, а не просьба установить произвольный старый выпуск.
Не заменяйте его на `--stable`/`latest` при воспроизведении этого руководства.
Пакеты Entware и меню загрузки ядер остаются внешними источниками: запишите
фактические версии и выберите ядро явно. При иной версии XKeen перечитайте её
документацию до продолжения.
В интерактивных вопросах выбирайте **по названию**, номера меню могут меняться:

| Вопрос | Выбор для этой сборки |
| --- | --- |
| Ядро | Xray; версию 26.10.29, при необходимости пункт ручного выбора |
| GeoSite | Re:filter и ZKeen |
| GeoIP | ZKeenIP |
| Исключить российские IP/дополнительные политики | Не добавлять новый слой исключений без необходимости |
| Автозапуск | Пока выключить |
| Расписание geodata | Пока выключить; одно задание добавим после проверки |
| Автообновление ядра | Пока выключить, чтобы версия не менялась во время диагностики |

Не запускайте шаблонный прокси после установки. Проверьте `xkeen -v`, `xray version`,
отсутствие запущенного тестового перехвата и наличие geodata:

```sh
ls -l /opt/etc/xray/dat/geosite_refilter.dat /opt/etc/xray/dat/geosite_zkeen.dat /opt/etc/xray/dat/geoip_zkeenip.dat
```

Для установки/добавления этих списков в XKeen 2.1 есть `xkeen -g`, для обновления
`xkeen -ug`; сначала проверьте локальную справку. Не переименовывайте случайные
базы в нужные имена: содержимое должно иметь используемые категории.

## 9. Установить конфиг роутера и списки перехвата

XKeen загружает **весь** `/opt/etc/xray/configs/`. Наш `00-home.json` содержит все
секции. Перед его копированием сохраните каталог и уберите конфликтующие шаблонные
JSON в резерв **вне** configs. Для новой установки без своих профилей пример:

```sh
# Entware shell; рабочий Xray здесь ещё не запущен.
task_backup="/opt/home-xray-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 "$task_backup"
cp -pR /opt/etc/xray/configs "$task_backup/configs"
cp -pR /opt/etc/xkeen "$task_backup/xkeen"
cp -p /opt/etc/init.d/S05xkeen "$task_backup/S05xkeen"
# Только для новой установки: все шаблоны уже сохранены выше.
mkdir -m 700 "$task_backup/inactive-json"
for task_file in /opt/etc/xray/configs/*.json; do
  [ ! -f "$task_file" ] || mv "$task_file" "$task_backup/inactive-json/"
done
```

На существующей установке вместо массового перемещения вручную слейте свои
нужные правила и сохраните один набор inbounds/outbounds. Не используйте этот блок
для работающего чужого профиля.

Передайте с компьютера `generated/router/00-home.json` в
`/opt/etc/xray/configs/00-home.json` через авторизованный SFTP/SSH. При SCP к старому
Dropbear может требоваться `scp -O -P YOUR_ENTWARE_PORT ...`; порт не угадывайте.
Не используйте анонимную сетевую папку для передачи секретов.

На роутере установите `chmod 600 /opt/etc/xray/configs/00-home.json`.
В существующий `/opt/etc/xkeen/ip_exclude.lst` **добавьте**, сохранив другие записи:
IP своего РФ-входа, IP иностранного выхода и используемых прямых DNS. По одному
адресу на строку. При DNS-именах узлов внесите их действующие адреса и предусмотрите
обновление исключений при смене IP. Для первого повторяемого варианта проще
фиксированные адреса VPS. Адрес LAN-клиента не добавляйте — иначе исключите его
из проксирования целиком.

В `/opt/etc/xkeen/port_proxying.lst` для начального варианта:

```text
22
80
443
3478
5222:5223
5228
19302:19309
```

Это только порты, передаваемые Xray для **дальнейшего выбора** DIRECT/VPN.
Остальные порты идут по обычной таблице маршрутизации. Не объявляйте это полным
туннелем и не обещайте, что любой IP из дополнения будет перехвачен на любом порту.
Существующий режим port-exclude не смешивайте с port-proxying; его копия сохранена.

Для выборочной обработки всей LAN используйте штатный Hybrid без ограничения
отдельной пользовательской политикой XKeen. Проверьте его конфигурацию и справку
своей версии, не назначайте весь домашний трафик новому внешнему default gateway.
Если в панели уже есть политика `xkeen`, `xkeen_full` или дополнительные политики
XKeen, проверьте их действие: они могут ограничить обработку выбранными клиентами
или принудительно направить назначения в прокси. Не удаляйте чужие политики;
согласуйте область и проверьте сообщение о ней при запуске.
Гостевой сегмент и устройства с отдельной политикой проверяются отдельно.

```sh
XRAY_LOCATION_ASSET=/opt/etc/xray/dat /opt/sbin/xray run -test -confdir /opt/etc/xray/configs
```

Ожидается успешная проверка всего каталога. Если нет файла/category или есть
дубликаты тегов, сначала исправьте их. IPv6 в опорной схеме не проверен: определите
его фактическое состояние и отдельно согласуйте поддерживаемую схему либо временное
исключение IPv6. Не запускайте экспериментальное глобальное отключение вслепую.

## 10. Подготовить реальный откат

Штатный `rollback-router.sh` подходит **только для перехода с сохранённого OpenVPN
и обычного DNS53-профиля** с namespace XKeen `xkeen_rule`/таблица `111`.
Он не восстанавливает прошивку/USB/чужие политики и не создаёт VPN из ничего.
Если у вас DoH/DoT, несколько меняемых сегментов, другой старый VPN или namespace,
сначала подготовьте соответствующий исходному состоянию вариант восстановления.

На компьютере скопируйте `configs/rollback.example.json` в `rollback.local.json`,
заполните исходными значениями по разделу 2. Если DNS не меняются, old/new могут
содержать одинаковый фактический набор. Передайте на роутер:

| Из проекта / закрытой папки | В Entware |
| --- | --- |
| `rollback.local.json` | `/opt/etc/home-xray/rollback.json` |
| `scripts/rollback-router.sh` | `/opt/etc/home-xray/rollback-router.sh` |
| `scripts/update-geodata.sh` | `/opt/etc/home-xray/update-geodata.sh` |

Целевой каталог создайте заранее через `mkdir -p /opt/etc/home-xray` и
`chmod 700 /opt/etc/home-xray`. Затем на роутере:

```sh
chmod 600 /opt/etc/home-xray/rollback.json
chmod 700 /opt/etc/home-xray/rollback-router.sh /opt/etc/home-xray/update-geodata.sh
sh -n /opt/etc/home-xray/rollback-router.sh
jq -e '.old_interface and .dns_profile and (.old_dns | length > 0) and (.new_dns | length > 0)' /opt/etc/home-xray/rollback.json
```

Это синтаксическая проверка, не доказательство корректности исходных значений.
Сверьте их с панелью/копией и проверьте доступность старого VPN до перехода.
Не запускайте сам откат ради «проверки», если старый доступ уже работает.

Перед переключением на роутере запустите защиту на десять минут:

```sh
rm -f /opt/etc/home-xray/confirmed
nohup sh -c 'sleep 600; exec /opt/etc/home-xray/rollback-router.sh --if-unconfirmed' </dev/null >/opt/etc/home-xray/guard.log 2>&1 &
task_guard_pid=$!
kill -0 "$task_guard_pid"
```

Запишите PID и время. Проверка `kill -0` должна быть успешна. Через десять минут
без маркера сценарий попытается вернуть OpenVPN и DNS. Это не постоянный watchdog
и не надёжная защита от отключения питания/перезагрузки. Для длинной приёмки сначала
пройдите короткую проверку, затем организуйте дальнейшее наблюдение с доступным
ручным откатом. Не оставляйте старый таймер, который отменит успешный длинный тест.

## 11. Переключить выборочную домашнюю сеть

1. Сохраните маршрут провайдера по умолчанию и текущий канал управления.
2. Если DNS зависят от старого AntiZapret, в системном и назначенном сегменту
   профилях замените их на доступные **обычные реальные** резолверы, записанные
   как `new_dns`. При доступном обычном DNS менять его ради установки не нужно.
   Пример DNS53-команд в Entware для **своего** профиля и адресов:

   ```sh
   /bin/ndmc -c 'dns-proxy filter profile YOUR_DNS_PROFILE dns53 no upstream YOUR_OLD_DNS'
   /bin/ndmc -c 'dns-proxy filter profile YOUR_DNS_PROFILE dns53 upstream YOUR_NEW_DNS'
   ```

   Повторите по реальным адресам; ответ не должен содержать ошибку. DoH/DoT
   настраиваются иначе. Автоматически отключать защищённый DNS браузера не нужно:
   при сбое сначала докажите, какой путь/правило обходится.
3. Выключите **только прежний** OpenVPN-интерфейс, не удаляя профиль/сертификаты.
   В Entware пример: `/bin/ndmc -c 'interface YOUR_OLD_OPENVPN_INTERFACE down'`.
   Затем сразу запустите `/opt/etc/init.d/S05xkeen start on`. Эти два действия
   выполните в пределах работающего таймера; ожидается один запущенный Xray,
   режим Hybrid и отсутствие ошибок. Не держите оба прозрачных перехвата активными.
4. На домашнем устройстве без собственного VPN проверьте обычные сайты, ChatGPT
   и отправку сообщения, Nexus и несколько минут YouTube. Подробный набор —
   [ACCEPTANCE.md](ACCEPTANCE.md). VPN не появится отдельной строкой OpenVPN:
   он работает внутри Entware. Не включайте ради этого «Другие подключения».
5. При сбое: выполните `sh /opt/etc/home-xray/rollback-router.sh` через сохранённый
   доступ либо дождитесь исправного таймера. Проверьте возвращение прежнего VPN,
   DNS и приложений. Не продолжайте на сломанной сети.
6. После короткой успешной проверки, пока связь сохранена, отмените отложенный
   откат: `touch /opt/etc/home-xray/confirmed`. Проведите 30-минутную приёмку,
   сохраняя готовый ручной откат. При плохом результате используйте его.

Если старый AntiZapret возвращал подменные IP, приложения могут держать их в кэше.
Перезапустите приложение, при необходимости устройство. Не закрепляйте CDN-IP
навсегда вместо устранения подтверждённой зависимости от старого DNS.

Обычный `curl` из Entware проверяет трафик **самого роутера**, для которого правила
перехвата могут отличаться от LAN. Приёмку домашней сети проводите с компьютера
или телефона в нужном сегменте; успешный запрос из shell роутера её не заменяет.

## 12. Сохранить, обновлять списки и проверить загрузку

Только после приёмки включите автозапуск XKeen. В 2.1 для этого есть интерактивный
`xkeen -auto`: **проверьте текущее состояние**, это переключатель, повторное
выполнение может выключить его. Убедитесь, что `start_auto` в
`/opt/etc/init.d/S05xkeen` стал `on`. Не создавайте второй startup-script.
Сохраните Keenetic: `/bin/ndmc -c 'system configuration save'` и проверьте ответ.

Один раз выполните `/opt/etc/home-xray/update-geodata.sh`, проверьте возврат,
процесс Xray и приложения. В существующий crontab Entware добавьте **одну** строку,
сохраняя другие задания и не дублируя штатное расписание XKeen:

```cron
23 4 * * * /opt/etc/home-xray/update-geodata.sh
```

Это 04:23 по часовому поясу роутера. Проверьте работу службы cron. Обёртка сохраняет
предыдущие dat и возвращает их, если ядро после обновления не запущено; она не
гарантирует семантическую правильность каждого нового домена. Личные дополнения
хранятся в вашем JSON/локальных исходниках и не заменяются geodata. Для их изменения
перегенерируйте в новом каталоге, проверьте и установите JSON с сохранением копии.

В отдельное разрешённое окно перезагрузите роутер штатно и проверьте `/opt`, один
процесс Xray, прямой интернет и выбранные приложения. До этой проверки пометьте
автозапуск после reboot как **NOT TESTED**, даже если флаг включён.
Заполните [итоговый чек-лист](ACCEPTANCE.md), оставьте закрытые копии и команду
отката. Не продлевайте аренду VPS без воли владельца и учитывайте конец тестового срока.

## Если установка не прошла

Не повторяйте всё сначала. Найдите первый неуспешный этап в отчёте, сохраните
последнее работавшее состояние и используйте [диагностику](DIAGNOSTICS.md).
Безопасно остановить только наши новые VPS-службы можно командами
`systemctl disable --now home-xray-entry.service` на РФ и соответствующей
`home-xray-exit.service` на выходе. Не удаляйте VPS, файлы, ключи и правила других
задач. Закройте лишь добавленные вами порты по сохранённому списку изменений,
когда новая цепочка больше не используется.
