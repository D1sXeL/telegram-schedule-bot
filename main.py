import json
import os
import time
import pytz
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from aiogram.utils.exceptions import TerminatedByOtherGetUpdates
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from bs4 import BeautifulSoup
import requests
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import math


token = os.environ.get("TOKEN")
bot = Bot(token=token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# Класс связанный с группами студентов
class StudentGroup:
    name = "student"
    url = "https://omacademy.ru/rasp-new/Website-students/cg.htm"

    # Получение необработанных данных
    @property
    async def get_data(self):
        page = requests.get(self.url)
        page.encoding = "utf-8"

        soup = BeautifulSoup(page.text, "html.parser")

        return soup

    # Обработка данных в формат json
    @property
    async def conversion_data(self):
        if await self.check_update:
            data = await self.get_data
            name_list = {"Обновлено": datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%d.%m.%Y %H:%M"),
                         "Группы" : {}}

            for i in data.findAll("a", class_="z0"):
                if i.text == "Заявка" or i.text == "Совещание":
                    pass
                else:
                    name_list["Группы"][i.text] = i.attrs['href']

            await self.write_file(name_list)

            return name_list
        else:
            data = await self.read_file

            return data

    # Проверка на существование файла с группами
    @property
    async def exists_file(self):
        if not os.path.exists("json"):
            os.mkdir("json")

        if not os.path.exists(f"json/all_{self.name}_group.json"):
            with open(f"json/all_{self.name}_group.json", "w", encoding="utf-8") as file:
                file.write("{}")
                file.close()
            return True

    # Запись данных в в файл
    async def write_file(self, data):
        with open(f"json/all_{self.name}_group.json", "w", encoding="utf-8") as file:
            json.dump(data, file)
            file.close()

    # Получение данных из файла
    @property
    async def read_file(self):
        with open(f"json/all_{self.name}_group.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            file.close()

        return data

    # Проверка на необходимость обновления данных. Данные обновляются при условии, что давность данных превышает 2 часа
    @property
    async def check_update(self):
        if await self.exists_file:
            return True

        date_now = datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%d.%m.%Y %H:%M")

        with open(f"json/all_{self.name}_group.json", "r", encoding="utf-8") as file:
            json_data = json.load(file)
            file.close()

        date_update = json_data["Обновлено"]
        result = str(datetime.datetime.strptime(date_update, "%d.%m.%Y %H:%M") - datetime.datetime.strptime(date_now, "%d.%m.%Y %H:%M"))

        if result[:1] == "-":
            result = str(datetime.datetime.strptime(date_now, "%d.%m.%Y %H:%M") - datetime.datetime.strptime(date_update, "%d.%m.%Y %H:%M"))
        if result[1] == ":":
            result = "0" + result

        if int(result[:2]) >= 2 or result.find("day") != -1:
            return True
        else:
            return False


# Класс связанный с преподавателями
class TeacherGroup(StudentGroup):
    name = "teacher"
    url = "https://omacademy.ru/rasp-new/Website-students/cp.htm"


# Класс связанный с расписанием для студента
class StudentsSchedule:
    def __init__(self, url, name_group):
        self.__url = f"https://omacademy.ru/rasp-new/Website-students/{url}"
        self.name_group = name_group
        self.type = "student"

    # Получение необработанных данных
    @property
    async def get_data(self):
        page = requests.get(self.__url)
        page.encoding = "utf-8"

        soup = BeautifulSoup(page.text, "html.parser")

        return soup

    # Проверка на существование файлов с расписанием определенной группы
    @property
    async def check_exists(self):
        if not os.path.exists(f'./json/{self.type}'):
            os.mkdir(f'./json/{self.type}')

        if not os.path.exists(f'./json/{self.type}/{self.name_group}.json'):
            with open(f'./json/{self.type}/{self.name_group}.json', 'w', encoding="utf-8") as file:
                file.write('{}')
                file.close()
            return True

    # Запись данных в файл
    async def write_file(self, data=None):
        await self.check_exists

        with open(f'./json/{self.type}/{self.name_group}.json', 'w', encoding="utf-8") as file:
            if data is None:
                data = await self.conversion_to_json
            json.dump(data, file)
            file.close()

    # Проверка на необходимость обновления данных. Данные обновляются при условии, что давность данных превышает 2 часа
    @property
    async def check_update(self):
        await self.check_exists

        with open(f'./json/{self.type}/{self.name_group}.json', 'r', encoding="utf-8") as file:
            data = json.load(file)
            file.close()

        if not data:
            await self.check_change
            return True

        date_now = datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%d.%m.%Y %H:%M")
        time_update_list = data["Обновлено"]

        result = str(datetime.datetime.strptime(date_now, "%d.%m.%Y %H:%M") - datetime.datetime.strptime(time_update_list, "%d.%m.%Y %H:%M"))

        if result[:1] == "-":
            result = str(datetime.datetime.strptime(time_update_list, "%d.%m.%Y %H:%M")-datetime.datetime.strptime(date_now, "%d.%m.%Y %H:%M"))

        if int(result[:1]) >= 1 or str(result).find("day") != -1:
            await self.check_change
            return False
        else:
            return False

    # Получение данных из файла
    async def get_data_file(self, check_update=True):
        if check_update:
            if await self.check_update:
                await self.write_file()
        else:
            await self.check_exists

        with open(f'./json/{self.type}/{self.name_group}.json', 'r', encoding="utf-8") as file:
            data = json.load(file)
            file.close()

        return data

    # Преобразование данных в формат json
    @property
    async def conversion_to_json(self):
        data = await self.get_data
        date_now = datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%d.%m.%Y %H:%M")

        data_schedule = dict()
        data_schedule["Обновлено"] = date_now
        data_schedule["Расписание"] = {}
        date = date_now[:10]

        data = data.findAll('tr')

        for i in data:
            if i.td.text.find(str(datetime.datetime.now(pytz.timezone('Europe/Moscow')).year)) != -1:
                data_schedule["Расписание"][i.td.text[:10]] = {
                    "День": str(i.td.text[-4:][:2]),
                    "1": {"Кабинет": "", "Наименование": "", "Преподаватель": "", "Время": ""},
                    "2": {"Кабинет": "", "Наименование": "", "Преподаватель": "", "Время": ""},
                    "3": {"Кабинет": "", "Наименование": "", "Преподаватель": "", "Время": ""},
                    "4": {"Кабинет": "", "Наименование": "", "Преподаватель": "", "Время": ""},
                    "5": {"Кабинет": "", "Наименование": "", "Преподаватель": "", "Время": ""},
                    "6": {"Кабинет": "", "Наименование": "", "Преподаватель": "", "Время": ""},
                    "7": {"Кабинет": "", "Наименование": "", "Преподаватель": "", "Время": ""}}

        for i in data:
            if i.td.text.find(str(datetime.datetime.now(pytz.timezone('Europe/Moscow')).year)) != -1:
                date = i.td.text[:10]

            if i.find("td", class_="ur"):
                if i.td.text.find("Пара") == -1:
                    temporary_number = "1"
                else:
                    temporary_number = i.td.text[:1]

                # Поиск наличия подгрупп
                pgr = i.findAll("td", attrs={"class": ["nul", "ur"]})
                test = i.findAll("td", class_="hd")

                if len(pgr) >= 2:
                    data_schedule["Расписание"][date][temporary_number] = {
                        "1 подгруппа": {"Кабинет": "", "Наименование": "", "Преподаватель": "", "Время": ""},
                        "2 подгруппа": {"Кабинет": "", "Наименование": "", "Преподаватель": "", "Время": ""}}

                    for j in test:
                        if j.text.find("Пара") != -1:
                            data_schedule["Расписание"][date][temporary_number]["1 подгруппа"]["Время"] = \
                                j.text.split(":")[1]

                            data_schedule["Расписание"][date][temporary_number]["2 подгруппа"]["Время"] = \
                                j.text.split(":")[1]

                    count = 1
                    for j in pgr:
                        if j.attrs['class'] == ['nul']:
                            count += 1
                        else:
                            temp = data_schedule["Расписание"][date][temporary_number][f"{count} подгруппа"]
                            temp["Кабинет"] = j.find("a", class_="z2").text

                            temp["Наименование"] = j.a.text

                            temp["Преподаватель"] = ", ".join(t.text for t in j.findAll("a", class_="z3"))

                            count += 1
                    # data_schedule["Обновлено"] = date_now
                else:
                    temp = data_schedule["Расписание"][date][temporary_number]

                    for j in test:
                        if j.text.find("Пара") != -1:
                            temp["Время"] = j.text.split(":")[1]

                    temp_data = i.find("td", class_="ur")

                    temp["Наименование"] = temp_data.a.text

                    temp["Преподаватель"] = ", ".join(t.text for t in temp_data.findAll("a", class_="z3"))
                    temp["Кабинет"] = temp_data.find("a", class_="z2").text
                    # data_schedule["Обновлено"] = date_now
        return data_schedule

    # Преобразование данных в готовый текст с учетом пользовательских настроек
    async def conversion_to_text(self, user_id):
        data = await self.get_data_file()

        finished_text = dict()
        data_schedule = data["Расписание"]

        data_user = (await User(self.type, user_id).get_data)[str(user_id)]['format_text']

        for key in data_schedule:
            finished_text[key] = ""
            for value in data_schedule[key]:
                temp_arr = [i for i in data_schedule[key][value]]

                if value == "День":
                    finished_text[key] += f"{key} - {data_schedule[key][value]}\n"
                elif temp_arr[0].find("подгруппа") != -1:
                    for i in temp_arr:
                        temp = data_schedule[key][value][i]
                        if temp['Наименование'] != "" or temp['Кабинет'] != "" or temp['Преподаватель'] != "":
                            finished_text[key] += f"{value} Пара <b>({temp['Время']})</b>\n{i}\n"
                            if data_user['name']:
                                finished_text[key] += f"{temp['Наименование']}"
                            if data_user['cabinet']:
                                finished_text[key] += f"\nКабинет - <b>{temp['Кабинет']}</b>"
                            if data_user['teacher']:
                                finished_text[key] += f"\n{temp['Преподаватель']}"
                            finished_text[key] += "\n-------------------------\n"
                else:
                    if data_schedule[key][value]['Наименование'] != "" or data_schedule[key][value]['Кабинет'] != "" or data_schedule[key][value]['Преподаватель'] != "":
                        data = data_schedule[key][value]

                        finished_text[key] += f"{value} Пара <b>({data['Время']})</b>\n"
                        if data_user['name']:
                            finished_text[key] += f"{data['Наименование']}"
                        if data_user['cabinet']:
                            finished_text[key] += f"\nКабинет - <b>{data['Кабинет']}</b>"
                        if data_user['teacher']:
                            finished_text[key] += f"\n{data['Преподаватель']}"
                        finished_text[key] += "\n-------------------------\n"

            if len(finished_text[key]) <= 16:
                finished_text[key] += "Выходной день"
            else:
                finished_text[key] = finished_text[key][:-1]
        return finished_text

    # Преобразование данных в готовый текст для оповещения
    async def conversion_to_text_notification(self, data):
        finished_text = dict()
        data_schedule = data

        for key in data_schedule:
            finished_text[key] = ""
            for value in data_schedule[key]:
                temp_arr = [i for i in data_schedule[key][value]]

                if value == "День":
                    finished_text[key] += f"{key} - {data_schedule[key][value]}\n"
                elif temp_arr[0].find("подгруппа") != -1:
                    for i in temp_arr:
                        temp = data_schedule[key][value][i]
                        if temp['Наименование'] != "" or temp['Кабинет'] != "" or temp['Преподаватель'] != "":
                            finished_text[key] += f"{value} Пара <b>({temp['Время']})</b>\n{i}\n"
                            finished_text[key] += f"{temp['Наименование']}"
                            finished_text[key] += f"\nКабинет - <b>{temp['Кабинет']}</b>"
                            finished_text[key] += f"\n{temp['Преподаватель']}"
                            finished_text[key] += "\n-------------------------\n"
                else:
                    if data_schedule[key][value]['Наименование'] != "" or data_schedule[key][value]['Кабинет'] != "" or data_schedule[key][value]['Преподаватель'] != "":
                        data = data_schedule[key][value]

                        finished_text[key] += f"{value} Пара <b>({data['Время']})</b>\n"
                        finished_text[key] += f"{data['Наименование']}"
                        finished_text[key] += f"\nКабинет - <b>{data['Кабинет']}</b>"
                        finished_text[key] += f"\n{data['Преподаватель']}"
                        finished_text[key] += "\n-------------------------\n"

            if len(finished_text[key]) <= 16:
                finished_text[key] += "Выходной день"
            else:
                finished_text[key] = finished_text[key][:-1]

            return finished_text

    # Проверка на наличие изменений
    @property
    async def check_change(self):
        print("Check changes")
        data_old = await self.get_data_file(check_update=False)
        if data_old == dict():
            return
        data_new = await self.conversion_to_json

        await self.write_file(data_new)

        change = {}
        temp_change = False
        for i in data_new['Расписание']:
            change[i] = data_new['Расписание'][i]
            change[i]['change'] = "false"
            temp = datetime.datetime(int(i[-4:]), int(i[-7:-5:]), int(i[:2])) - datetime.datetime.now()

            if temp.days == -1 and temp.seconds / 60 / 60 <= 24 or temp.days >= 0:
                for i1 in data_new['Расписание'][i]:
                    if i1 != "День" and i1 != "change":
                        temp_data_new = data_new['Расписание'][i][i1]
                        try:
                            temp_data_old = data_old['Расписание'][i][i1]
                        except KeyError:
                            break

                        if '1 подгруппа' in data_new['Расписание'][i][i1]:
                            if temp_data_new['1 подгруппа']['Кабинет'] != temp_data_old['1 подгруппа']['Кабинет']:
                                change[i][i1]['1 подгруппа']['Кабинет'] = f"<u>{temp_data_old['1 подгруппа']['Кабинет']} -> {temp_data_new['1 подгруппа']['Кабинет']}</u>"
                                change[i]['change'] = 'true'
                                temp_change = True

                            if temp_data_new['1 подгруппа']['Наименование'] != temp_data_old['1 подгруппа']['Наименование']:
                                change[i][i1]['1 подгруппа']['Наименование'] = f"<u>{temp_data_old['1 подгруппа']['Наименование']}\n -> \n{temp_data_new['1 подгруппа']['Наименование']}</u>"
                                change[i]['change'] = 'true'
                                temp_change = True

                            if temp_data_new['1 подгруппа']['Преподаватель'] != temp_data_old['1 подгруппа']['Преподаватель']:
                                change[i][i1]['1 подгруппа']['Преподаватель'] = f"<u>{temp_data_old['1 подгруппа']['Преподаватель']}\n -> \n{temp_data_new['1 подгруппа']['Преподаватель']}</u>"
                                change[i]['change'] = 'true'
                                temp_change = True

                        elif '2 подгруппа' in data_new['Расписание'][i][i1]:
                            if temp_data_new['2 подгруппа']['Кабинет'] != temp_data_old['2 подгруппа']['Кабинет']:
                                change[i][i1]['2 подгруппа'][
                                    'Кабинет'] = f"<u>{temp_data_old['2 подгруппа']['Кабинет']} -> {temp_data_new['2 подгруппа']['Кабинет']}</u>"
                                change[i]['change'] = 'true'
                                temp_change = True

                            if temp_data_new['2 подгруппа']['Наименование'] != temp_data_old['2 подгруппа'][
                                'Наименование']:
                                change[i][i1]['2 подгруппа'][
                                    'Наименование'] = f"<u>{temp_data_old['2 подгруппа']['Наименование']}\n -> \n{temp_data_new['2 подгруппа']['Наименование']}</u>"
                                change[i]['change'] = 'true'
                                temp_change = True

                            if temp_data_new['2 подгруппа']['Преподаватель'] != temp_data_old['2 подгруппа'][
                                'Преподаватель']:
                                change[i][i1]['2 подгруппа'][
                                    'Преподаватель'] = f"<u>{temp_data_old['2 подгруппа']['Преподаватель']}\n -> \n{temp_data_new['2 подгруппа']['Преподаватель']}</u>"
                                change[i]['change'] = 'true'
                                temp_change = True

                        else:
                            if temp_data_new['Кабинет'] != temp_data_old['Кабинет']:
                                change[i][i1]['Кабинет'] = f"<u>{temp_data_old['Кабинет']} -> {temp_data_new['Кабинет']}</u>"
                                change[i]['change'] = 'true'
                                temp_change = True

                            if temp_data_new['Наименование'] != temp_data_old['Наименование']:
                                change[i][i1][
                                    'Наименование'] = f"<u>{temp_data_old['Наименование']}\n -> \n{temp_data_new['Наименование']}</u>"
                                change[i]['change'] = 'true'
                                temp_change = True

                            if temp_data_new['Преподаватель'] != temp_data_old['Преподаватель']:
                                change[i][i1][
                                    'Преподаватель'] = f"<u>{temp_data_old['Преподаватель']}\n -> \n{temp_data_new['Преподаватель']}</u>"
                                change[i]['change'] = 'true'
                                temp_change = True

        if temp_change is True:
            id_profile = await User(type=self.type).get_id_favourite(self.name_group)
        else:
            return

        if id_profile is None:
            return

        for i in change.copy():
            if change[i]['change'] == 'false':
                del change[i]
            else:
                del change[i]['change']

        data = await self.conversion_to_text_notification(change)

        for id in id_profile:
            await bot.send_message(chat_id=id, text=f"Оповещение об изменении в расписании\nГруппа - {self.name_group}")
            for j in data:
                await bot.send_message(chat_id=id, text=data[j], parse_mode=ParseMode.HTML)


# Класс связанный с расписанием преподавателей
class TeacherSchedule:
    def __init__(self, url, name_group):
        self.__url = f"https://omacademy.ru/rasp-new/Website-students/{url}"
        self.type = 'teacher'
        self.name_group = name_group

    # Получение необработанных данных
    @property
    async def get_data(self):
        page = requests.get(self.__url)
        page.encoding = "utf-8"

        soup = BeautifulSoup(page.text, "html.parser")

        return soup

    # Проверка на сущестование файлов преподавателей
    @property
    async def check_exists(self):
        if not os.path.exists(f'./json/{self.type}'):
            os.mkdir(f'./json/{self.type}')

        if not os.path.exists(f'./json/{self.type}/{self.name_group}.json'):
            with open(f'./json/{self.type}/{self.name_group}.json', 'w', encoding="utf-8") as file:
                file.write('{}')
                file.close()
            return True

    # Запись данных в файл
    async def write_file(self, data=None):
        await self.check_exists

        with open(f'./json/{self.type}/{self.name_group}.json', 'w', encoding="utf-8") as file:
            if data is None:
                data = await self.conversion_to_json
            json.dump(data, file)
            file.close()

    # Проверка на неоходимость обновления данных. Данные обновляются при условии, что давность данных превышает 1 часа
    @property
    async def check_update(self):
        await self.check_exists

        with open(f'./json/{self.type}/{self.name_group}.json', 'r', encoding="utf-8") as file:
            data = json.load(file)
            file.close()

        if not data:
            await self.check_change
            return True

        date_now = datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%d.%m.%Y %H:%M")
        time_update_list = data["Обновлено"]

        result = str(
            datetime.datetime.strptime(date_now, "%d.%m.%Y %H:%M") - datetime.datetime.strptime(time_update_list,
                                                                                                "%d.%m.%Y %H:%M"))

        if result[:1] == "-":
            result = str(
                datetime.datetime.strptime(time_update_list, "%d.%m.%Y %H:%M") - datetime.datetime.strptime(date_now,
                                                                                                            "%d.%m.%Y %H:%M"))

        if int(result[:1]) >= 1 or str(result).find("day") != -1:
            await self.check_change
            return False
        else:
            return False

    # Получение данных из файла
    async def get_data_file(self, check_update=True):
        if check_update:
            if await self.check_update:
                await self.write_file()
        else:
            await self.check_exists

        with open(f'./json/{self.type}/{self.name_group}.json', 'r', encoding="utf-8") as file:
            data = json.load(file)
            file.close()

        return data

    # Преобразование данных в формат json
    @property
    async def conversion_to_json(self):
        data = await self.get_data
        data_json = dict()
        date_now = datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%d.%m.%Y %H:%M")

        data_json["Обновлено"] = date_now
        data_json["Расписание"] = dict()

        temp = data.findAll("td", class_="hd")

        for i in temp:
            if i.text.find(str(datetime.datetime.now(pytz.timezone('Europe/Moscow')).year)) != -1:
                data_json["Расписание"][i.text[:10]] = {
                    "День": str(i.text[-4:][:2]),
                    "1": {"Кабинет": "", "Группы": "", "Наименование": "", "Время": ""},
                    "2": {"Кабинет": "", "Группы": "", "Наименование": "", "Время": ""},
                    "3": {"Кабинет": "", "Группы": "", "Наименование": "", "Время": ""},
                    "4": {"Кабинет": "", "Группы": "", "Наименование": "", "Время": ""},
                    "5": {"Кабинет": "", "Группы": "", "Наименование": "", "Время": ""},
                    "6": {"Кабинет": "", "Группы": "", "Наименование": "", "Время": ""},
                    "7": {"Кабинет": "", "Группы": "", "Наименование": "", "Время": ""}
                }

        data = data.findAll("tr")

        for i in data:
            if i.td.text.find(str(datetime.datetime.now(pytz.timezone('Europe/Moscow')).year)) != -1:
                date = i.td.text[:10]

            if i.find('td', class_="ur"):

                if i.td.text.find("Пара") == -1:
                    temporary_number = "1"
                    data_json["Расписание"][date][temporary_number]["Время"] = "8.00-09.40"
                else:
                    temporary_number = i.td.text[:1]
                    data_json["Расписание"][date][temporary_number]["Время"] = i.td.text[-11:]

                try:
                    data_json["Расписание"][date][temporary_number]["Кабинет"] = i.find("a", class_="z2").text
                except AttributeError:
                    pass

                data_json["Расписание"][date][temporary_number]["Группы"] = ", ".join(t.text for t in i.findAll("a",
                                                                                                                class_=
                                                                                                                "z1"))

                data_json["Расписание"][date][temporary_number]["Наименование"] = i.find("a", class_="z3").text

        return data_json

    # Преобразование данных в готовый текст с учетом пользовательских настроек
    async def conversion_to_text(self, user_id):
        data = await self.get_data_file()

        finished_text = dict()
        data_schedule = data["Расписание"]

        data_user = (await User(self.type, user_id).get_data)[str(user_id)]['format_text']

        for key in data_schedule:
            finished_text[key] = ""
            for value in data_schedule[key]:
                if value == "День":
                    finished_text[key] += f"{key} - {data_schedule[key][value]}\n"
                else:
                    if data_schedule[key][value]['Наименование'] != "" or data_schedule[key][value]['Кабинет'] != "" or data_schedule[key][value]['Группы'] != "":
                        data = data_schedule[key][value]

                        finished_text[key] += f"{value} Пара <b>({data['Время']})</b>\n"

                        if data_user['name']:
                            finished_text[key] += f"{data['Наименование']}"
                        if data_user['cabinet']:
                            finished_text[key] += f"\nКабинет - <b>{data['Кабинет']}</b>"
                        if data_user['group']:
                            finished_text[key] += f"\nГруппы - <b>{data['Группы']}</b>"
                        finished_text[key] += "\n-------------------------\n"
            if len(finished_text[key]) <= 16:
                finished_text[key] += "Выходной день"
            else:
                finished_text[key] = finished_text[key][:-1]
        return finished_text

    # Преобразование данных в готовый текст для оповещения
    async def conversion_to_text_notification(self, data):
        finished_text = dict()

        for key in data:
            finished_text[key] = ""
            for value in data[key]:
                if value == "День":
                    finished_text[key] += f"{key} - {data[key][value]}\n"
                else:
                    if data[key][value]['Наименование'] != "" or data[key][value]['Кабинет'] != "" or data[key][value]['Группы'] != "":
                        temp = data[key][value]

                        finished_text[key] += f"{value} Пара <b>({temp['Время']})</b>\n"
                        finished_text[key] += f"{temp['Наименование']}"
                        finished_text[key] += f"\nКабинет - <b>{temp['Кабинет']}</b>"
                        finished_text[key] += f"\nГруппы - <b>{temp['Группы']}</b>"
                        finished_text[key] += "\n-------------------------\n"
            if len(finished_text[key]) <= 16:
                finished_text[key] += "Выходной день"
            else:
                finished_text[key] = finished_text[key][:-1]

        return finished_text

    # Проверка на наличие изменений
    @property
    async def check_change(self):
        data_old = await self.get_data_file(check_update=False)
        if data_old == dict():
            return
        data_new = await self.conversion_to_json
        await self.write_file(data_new)

        change = {}
        temp_change = False

        for i in data_new['Расписание']:
            change[i] = data_new['Расписание'][i]
            change[i]['change'] = "false"
            temp = datetime.datetime(int(i[-4:]), int(i[-7:-5:]), int(i[:2])) - datetime.datetime.now()

            if temp.days == -1 and temp.seconds / 60 / 60 <= 24 or temp.days >= 0:
                for i1 in data_new['Расписание'][i]:
                    if i1 != "День" and i1 != "change":
                        temp_data_new = data_new['Расписание'][i][i1]
                        try:
                            temp_data_old = data_old['Расписание'][i][i1]
                        except KeyError:
                            break

                        if temp_data_new['Кабинет'] != temp_data_old['Кабинет']:
                            change[i][i1][
                                'Кабинет'] = f"<u>{temp_data_old['Кабинет']} -> {temp_data_new['Кабинет']}</u>"
                            change[i]['change'] = 'true'
                            temp_change = True

                        if temp_data_new['Группы'] != temp_data_old['Группы']:
                            change[i][i1][
                                'Группы'] = f"<u>{temp_data_old['Группы']}\n -> \n{temp_data_new['Группы']}</u>"
                            change[i]['change'] = 'true'
                            temp_change = True

                        if temp_data_new['Наименование'] != temp_data_old['Наименование']:
                            change[i][i1][
                                'Наименование'] = f"<u>{temp_data_old['Наименование']}\n -> \n{temp_data_new['Наименование']}</u>"
                            change[i]['change'] = 'true'
                            temp_change = True

        if temp_change is True:
            id_profile = await User(type=self.type).get_id_favourite(self.name_group)
        else:
            return

        if id_profile is None:
            return

        for i in change.copy():
            if change[i]['change'] == 'false':
                del change[i]
            else:
                del change[i]['change']

        data = await self.conversion_to_text_notification(change)

        for id in id_profile:
            await bot.send_message(chat_id=id, text="Оповещение об изменении в расписании")
            for j in data:
                await bot.send_message(chat_id=id, text=data[j], parse_mode=ParseMode.HTML)


# Класс связанный с настройками пользователей
class User:
    def __init__(self, type, user_id=0):
        self.user_id = str(user_id)
        self.type = type

    # Проверка на существование файла
    @property
    async def check_exists(self):
        if not os.path.exists(f"json/{self.type}_settings.json"):
            with open(f"json/{self.type}_settings.json", "w", encoding="utf-8") as file:
                file.write("{}")
                file.close()

            return False
        else:
            return True

    # Получение данных. Проверка на существование. Создание файлов
    @property
    async def get_data(self):
        await self.check_exists

        with open(f"json/{self.type}_settings.json", "r+", encoding="utf-8") as file:
            temp = json.load(file)
            file.close()

        try:
            temp[self.user_id]
            return temp
        except KeyError:
            if self.type == "student":
                temp[self.user_id] = {"favourite_group": {},
                                 "format_text": {"name": 1, "cabinet": 1, "teacher": 1},
                                 "get_notifications": 0}
            else:
                temp[self.user_id] = {"favourite_group": {},
                                      "format_text": {"name": 1, "cabinet": 1, "group": 1},
                                      "get_notifications": 0}

        with open(f"json/{self.type}_settings.json", "w", encoding="utf-8") as file:
            json.dump(temp, file)
            file.close()

        return temp

    # Получение данных без всяких проверок
    @property
    async def get_data_file(self):
        if await self.check_exists:

            with open(f"json/{self.type}_settings.json", "r+", encoding="utf-8") as file:
                data = json.load(file)
                file.close()

            return data
        else:
            return None

    # Изменение данных пользователей в файле
    async def edit_data_user(self, data):
        user_id = self.user_id

        count = 0
        for i in data['format_text']:
            if data['format_text'][i] == 0:
                count += 1

        if count == 3:
            data['format_text']['name'] = 1

        with open(f"json/{self.type}_settings.json", "r+", encoding="utf-8") as file:
            temp = json.load(file)
            file.close()

        temp[user_id] = data

        with open(f"json/{self.type}_settings.json", "w", encoding="utf-8") as file:
            json.dump(temp, file)
            file.close()

    # Добавление избранной группы
    async def add_favourite_group(self, name, link):
        data = await self.get_data

        if data[self.user_id]["favourite_group"].get(name) == link:
            return False

        data[self.user_id]["favourite_group"][name] = link

        with open(f"json/{self.type}_settings.json", "w", encoding="utf-8") as file:
            json.dump(data, file)
            file.close()

        if self.type == "teacher":
            if await TeacherSchedule(url=link, name_group=name).check_exists:
                await TeacherSchedule(url=link, name_group=name).get_data_file()
        elif self.type == "student":
            if await StudentsSchedule(url=link, name_group=name).check_exists:
                await StudentsSchedule(url=link, name_group=name).get_data_file()

    # Удаление избранной группы
    async def remove_favourite_group(self, name):
        data = await self.get_data

        data[self.user_id]["favourite_group"].pop(name)

        with open(f"json/{self.type}_settings.json", "w", encoding="utf-8") as file:
            json.dump(data, file)
            file.close()

    # Получение айди пользователей для оповещения об изменениях
    async def get_id_favourite(self, name_group):
        data = await self.get_data_file
        id_profile = list()

        if data is None:
            return data

        for i in data:
            if data[i]['get_notifications'] == 1:
                if name_group in data[i]['favourite_group']:
                    id_profile.append(i)

        return id_profile

    # Получение айди пользователей с включенным оповещением об изменении расписания
    @property
    async def get_name_group_alert_enable(self):
        data = await self.get_data_file

        if data is None:
            return None

        groups = dict()

        for i in data:
            if data[i]['get_notifications'] == 1:
                for j in data[i]['favourite_group']:
                    if j in data[i]['favourite_group']:
                        groups[j] = data[i]['favourite_group'][j]

        return groups


# Класс необходим для ожидания сообщения от пользователя.
class Form(StatesGroup):
    name = State()


async def notification_schedule(data, id_profile):
    for id in id_profile:
        await bot.send_message(chat_id=id, text="Оповещение об изменении в расписании")
        for j in data:
            await bot.send_message(chat_id=id, text=data[j], parse_mode=ParseMode.HTML)

# Меню студента/преподавателя
async def markup_user(call, prefix="student"):
    markup = InlineKeyboardMarkup(row_width=3)

    markup.add(InlineKeyboardButton(text="Расписание", callback_data=f"{prefix}_schedule_menu"),
               InlineKeyboardButton(text="Расписание(избранное)", callback_data=f"{prefix}_schedule_favourite_menu"))
    markup.add(InlineKeyboardButton(text="Добавить в избранное", callback_data=f"{prefix}_favourite_view"),
               InlineKeyboardButton(text="Удалить из избранного", callback_data=f"{prefix}_favourite_remove"))
    markup.add(InlineKeyboardButton(text="Поиск", callback_data=f"{prefix}_search_main"))
    markup.add(InlineKeyboardButton(text="Настройки", callback_data=f"{prefix}_settings_main"))
    markup.add(InlineKeyboardButton(text="Вернуться обратно", callback_data="return_main"))
    if prefix == "student":
        text = "Меню студента"
    else:
        text = "Меню преподавателя"

    await call.message.edit_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)


# Главное меню
async def markup_menu(message, call=0):
    markup = InlineKeyboardMarkup(row_width=3)

    markup.add(InlineKeyboardButton(text="Студенту", callback_data="student_menu"),
               InlineKeyboardButton(text="Преподавателю", callback_data="teacher_menu"))

    if call == 0:
        await message.answer("-------------------------Главное Меню-------------------------", reply_markup=markup,
             parse_mode=ParseMode.HTML)
    else:
        await message.edit_text("-------------------------Главное Меню-------------------------", reply_markup=markup,
                             parse_mode=ParseMode.HTML)


async def view_group(call, prefix="student_schedule_group", step=None):
    max_size = 90
    temp = prefix.split('_')

    if temp[0] == "student":
        row_width = 3
        name_group = (await StudentGroup().conversion_data)['Группы']
    else:
        row_width = 1
        name_group = (await TeacherGroup().conversion_data)['Группы']

    markup = InlineKeyboardMarkup(row_width=row_width)
    length_arr = len(name_group)

    group_keys = list(name_group.keys())

    if step is None or step == 0:
        keys_group = []

        for i in range(0, max_size+1):
            try:
                keys_group.append(InlineKeyboardButton(text=f"{group_keys[i]}", callback_data=f"{prefix}_{name_group[group_keys[i]]}"))
            except IndexError:
                break

        markup.add(*keys_group)
        markup.add(InlineKeyboardButton(text=f"(1/{math.ceil(length_arr/max_size)})--->", callback_data=f"{temp[0]}_{temp[1]}_n_{i}"))
        markup.add(InlineKeyboardButton(text="Вернуться обратно", callback_data=f"return_{temp[0]}_menu"))

    elif step < 0:
        step *= -1
        keys_group = []

        for i in range(step, step+max_size):
            try:
                keys_group.append(InlineKeyboardButton(text=f"{group_keys[i]}",
                                                   callback_data=f"{prefix}_{name_group[group_keys[i]]}"))
            except IndexError:
                break

        markup.add(*keys_group)

        if 0 < step < length_arr:
            markup.add(InlineKeyboardButton(
                text=f"<---({round(length_arr / step)}/{math.ceil(length_arr / max_size)})",
                callback_data=f"{temp[0]}_{temp[1]}_b_{step-max_size}"))
            markup.add(InlineKeyboardButton(
                text=f"({math.ceil(step/max_size)}/{math.ceil(length_arr / step)})--->",
                callback_data=f"{temp[0]}_{temp[1]}_n_{step+max_size}"))

        elif max_size+step >= length_arr:
            markup.add(InlineKeyboardButton(
                text=f"<---({math.ceil(length_arr / max_size)}/{math.ceil(length_arr / max_size)})",
                callback_data=f"{temp[0]}_{temp[1]}_b_{step-max_size}"))

        elif length_arr - step <= 0:
            markup.add(InlineKeyboardButton(text=f"(1/{math.ceil(length_arr / max_size)})-->",
                                        callback_data=f"{temp[0]}_{temp[1]}_n_{step}"))

        markup.add(InlineKeyboardButton(text="Вернуться обратно", callback_data=f"return_{temp[0]}_menu"))

    elif step > 0:
        keys_group = []

        count = 0
        for i in range(step, step+max_size):
            try:
                keys_group.append(InlineKeyboardButton(text=f"{group_keys[i]}",
                                                       callback_data=f"{prefix}_{name_group[group_keys[i]]}"))
            except IndexError:
                break

            if count == max_size:
                break
            count += 1

        markup.add(*keys_group)
        if length_arr - step > 0 and max_size + step < length_arr:
            markup.add(InlineKeyboardButton(
                text=f"<---({math.ceil((step+step) / max_size)}/{math.ceil(length_arr / max_size)})",
                callback_data=f"{temp[0]}_{temp[1]}_b_{step-max_size}"))
            markup.add(InlineKeyboardButton(
                text=f"({math.ceil((step+step) / max_size)}/{math.ceil(length_arr / max_size)})--->",
                callback_data=f"{temp[0]}_{temp[1]}_n_{step+max_size}"))

        elif max_size+step >= length_arr:
            markup.add(InlineKeyboardButton(
                text=f"<---({math.ceil(length_arr / max_size)}/{math.ceil(length_arr / max_size)})",
                callback_data=f"{temp[0]}_{temp[1]}_b_{step-max_size}"))

        elif length_arr - step <= 0:
            markup.add(
                InlineKeyboardButton(text=f"(1/{math.ceil(length_arr / max_size)})-->",
                                     callback_data=f"{temp[0]}_{temp[1]}_n_{step+max_size}"))

        markup.add(InlineKeyboardButton(text="Вернуться обратно", callback_data=f"return_{temp[0]}_menu"))

    if temp[0] == "teacher":
        text = "------ Выберите преподавателя -------"
    else:
        text = "------ Выберите группу -------"
    await call.message.edit_text(text=text, reply_markup=markup,
                                          parse_mode=ParseMode.HTML)


async def period_schedule(call, prefix, group):
    markup = InlineKeyboardMarkup(row_width=3)

    markup.add(InlineKeyboardButton(text="Сегодня", callback_data=f"{prefix}_view_{group}_{0}"),
               InlineKeyboardButton(text="На завтра", callback_data=f"{prefix}_view_{group}_{1}"),
               InlineKeyboardButton(text="На 3 дня", callback_data=f"{prefix}_view_{group}_{3}"),
               InlineKeyboardButton(text="На 7 дней", callback_data=f"{prefix}_view_{group}_{7}"),
               InlineKeyboardButton(text="Полностью", callback_data=f"{prefix}_view_{group}_{14}"))
    markup.add(InlineKeyboardButton(text="Вернуться обратно", callback_data=f"return_{prefix}_group"))

    await call.message.edit_text(text="Выберите за какой период показать расписание", reply_markup=markup)


async def view_schedule(call, group, period, prefix):
    if prefix == "student":
        data_group = (await StudentGroup().conversion_data)['Группы']
        name_group = list(data_group.keys())[list(data_group.values()).index(group)]
        data = await StudentsSchedule(group, name_group).conversion_to_text(call.from_user.id)
    else:
        data_group = (await TeacherGroup().conversion_data)['Группы']
        name_group = list(data_group.keys())[list(data_group.values()).index(group)]
        data = await TeacherSchedule(group, name_group).conversion_to_text(call.from_user.id)

    if period > 0:
        count = 0
        for i in data:
            if period == 1:
                date = datetime.datetime.now(pytz.timezone('Europe/Moscow'))

                date += datetime.timedelta(days=1)
                await call.message.answer(text=data[date.strftime("%d.%m.%Y")], parse_mode=ParseMode.HTML)
                break

            temp = datetime.datetime(int(i[-4:]), int(i[-7:-5:]), int(i[:2])) - datetime.datetime.now()

            if temp.days == -1 and temp.seconds / 60 / 60 <= 24 or temp.days >= 0:
                await call.message.answer(text=data[i], parse_mode=ParseMode.HTML)
                count += 1

            if count == period:
                break
    else:
        markup = InlineKeyboardMarkup(row_width=3)
        data_keys = list(data.keys())

        for i in data:
            if int(i[:2]) == int(datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%d")):
                next_day = data_keys[data_keys.index(i)+1]
                markup.add(
                    InlineKeyboardButton(text=f"{next_day} ---->", callback_data=f"{prefix}_next_{next_day}_{group}"))
                await call.message.answer(text=data[i], reply_markup=markup, parse_mode=ParseMode.HTML)
                break


async def view_favourite_group(call, prefix):
    temp = prefix.split("_")
    if temp[0] == "student":
        row_width = 3
    else:
        row_width = 1

    data = (await User(temp[0], call.from_user.id).get_data)[str(call.from_user.id)]["favourite_group"]

    markup = InlineKeyboardMarkup(row_width=row_width)

    keys_group = []
    for i in data.items():
        keys_group.append(InlineKeyboardButton(text=i[0], callback_data=f"{prefix}_{i[1]}"))

    markup.add(*keys_group)
    markup.add(InlineKeyboardButton(text="Вернуться обратно", callback_data=f"return_{temp[0]}_menu"))

    await call.message.edit_text(text="Выберите группу", reply_markup=markup)


async def personal_settings_menu(call, prefix):
    markup = InlineKeyboardMarkup(row_width=3)

    if prefix == "student":
        markup.add(InlineKeyboardButton(text="Название", callback_data=f"{prefix}_settings_name"),
                   InlineKeyboardButton(text="Кабинет", callback_data=f"{prefix}_settings_cabinet"),
                   InlineKeyboardButton(text="Преподаватель", callback_data=f"{prefix}_settings_teacher"))
        markup.add(InlineKeyboardButton(text="Оповещение", callback_data=f"{prefix}_settings_notification"))

        markup.add(InlineKeyboardButton(text="Вернуться обратно", callback_data=f"return_{prefix}_menu"))

        data = (await User(prefix, call.from_user.id).get_data)[str(call.from_user.id)]
        temp = data['format_text']

        await call.message.edit_text((
                                    f"Настройки:\n\nФормат текста\n"
                                    f"Выводить название предмета: {temp['name']}\n"
                                    f"Выводить кабинет: {temp['cabinet']}\n"
                                    f"Выводить ФИО преподавателя: {temp['teacher']}"
                                    f"\n\nПолучать оповещение об изменениях в расписании(избранное): {data['get_notifications']}").replace("1", "✅").replace("0", "❌"),
                                reply_markup=markup)
    else:
        markup.add(InlineKeyboardButton(text="Название", callback_data=f"{prefix}_settings_name"),
                   InlineKeyboardButton(text="Кабинет", callback_data=f"{prefix}_settings_cabinet"),
                   InlineKeyboardButton(text="группы", callback_data=f"{prefix}_settings_groups"))
        markup.add(InlineKeyboardButton(text="Оповещение", callback_data=f"{prefix}_settings_notification"))

        markup.add(InlineKeyboardButton(text="Вернуться обратно", callback_data=f"return_{prefix}_menu"))

        data = (await User(prefix, call.from_user.id).get_data)[str(call.from_user.id)]
        temp = data['format_text']
        await call.message.edit_text((
                                         f"Настройки:\n\nФормат текста\n"
                                         f"Выводить название предмета: {temp['name']}\n"
                                         f"Выводить кабинет: {temp['cabinet']}\n"
                                         f"Выводить группы: {temp['group']}"
                                         f"\n\nПолучать оповещение об изменениях в расписании(избранное): {data['get_notifications']}").replace("1", "✅").replace(
            "0", "❌"), reply_markup=markup)


async def view_next_back_schedule(call, date, group, prefix):
    if prefix == "student":
        temp = (await StudentGroup().conversion_data)['Группы']
        name_group = list(temp.keys())[list(temp.values()).index(group)]

        data = await StudentsSchedule(group, name_group).conversion_to_text(call.from_user.id)
    else:
        temp = (await TeacherGroup().conversion_data)['Группы']
        name_group = list(temp.keys())[list(temp.values()).index(group)]
        data = await TeacherSchedule(group, name_group).conversion_to_text(call.from_user.id)

    markup = InlineKeyboardMarkup(row_width=3)

    data_keys = list(data.keys())
    for i in data_keys.copy():
        if int(i[:2]) < int(datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%d")):
            del data_keys[data_keys.index(i)]

    day = data_keys.index(date)

    if day == 0:
        next_day = data_keys[day + 1]
        markup.add(InlineKeyboardButton(text=f"{next_day} ---->", callback_data=f"{prefix}_next_{next_day}_{group}"))
    elif day == len(data_keys)-1:
        back_day = data_keys[day-1]
        markup.add(InlineKeyboardButton(text=f"<---- {back_day}", callback_data=f"{prefix}_next_{back_day}_{group}"))
    else:
        back_day = data_keys[day-1]
        next_day = data_keys[day+1]
        markup.add(InlineKeyboardButton(text=f"<---- {back_day} ", callback_data=f"{prefix}_next_{back_day}_{group}"),
            InlineKeyboardButton(text=f"{next_day} ---->", callback_data=f"{prefix}_next_{next_day}_{group}"))

    await call.message.edit_text(text=data[date], reply_markup=markup, parse_mode=ParseMode.HTML)


@dp.message_handler(state='*', commands='cancel')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    await state.finish()
    await message.reply('Поиск отменён!')


@dp.message_handler(state=Form.name)
async def process_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['name'] = message.text

    await state.finish()

    try:
        temp = (await StudentGroup().conversion_data)['Группы'][message.text]
        temp_name = "student"
    except KeyError:
        try:
            temp = (await TeacherGroup().conversion_data)['Группы'][message.text]
            temp_name = "teacher"
        except KeyError:
            await message.answer("Ошибка!")
            return False

    markup = InlineKeyboardMarkup(row_width=3)

    markup.add(InlineKeyboardButton(text="Добавить в избранное", callback_data=f"{temp_name}_search_add_{temp}"))
    markup.add(InlineKeyboardButton(text="Получить расписание", callback_data=f"{temp_name}_search_view_{temp}"))

    await message.answer(text="Выберите действие", reply_markup=markup)


@dp.callback_query_handler()
async def func1(call: types.CallbackQuery):
    req = call.data.split('_')
    print(req)

    if req[0] == "student":
        if req[1] == "menu":
            await markup_user(call)

        elif req[1] == "schedule" or req[1] == "s":
            if req[2] == 'menu':
                await view_group(call, req[0]+"_schedule_group")

            elif req[2] == 'group' or req[2] == "g":
                await period_schedule(call, req[0], req[3])

            elif req[2] == "favourite":
                await view_favourite_group(call, req[0]+"_favourite_group")

            elif req[2] == "n":
                await view_group(call, req[0]+"_s_g", int(req[3]))

            elif req[2] == "b":
                await view_group(call, req[0]+"_s_g", int(req[3])*-1)

        elif req[1] == "favourite" or req[1] == "f":
            if req[2] == "view":
                if len(req) == 3:
                    await view_group(call, req[0]+"_f_a")
                elif len(req) == 5:
                    await view_schedule(call, req[3], int(req[4]), req[0])

            elif req[2] == "group":
                await period_schedule(call, req[0]+"_favourite", req[3])

            elif req[2] == "append" or req[2] == "a":
                data_group = (await StudentGroup().conversion_data)['Группы']
                name_group = list(data_group.keys())[list(data_group.values()).index(req[3])]

                await User(req[0], call.from_user.id).add_favourite_group(name_group, req[3])

                await call.message.answer(f"Группа {name_group} была добавлена в избранное!")

            elif req[2] == "remove":
                if(len(req) == 3):
                    await view_favourite_group(call, req[0]+"_favourite_remove")
                else:
                    data_group = (await StudentGroup().conversion_data)['Группы']
                    name_group = list(data_group.keys())[list(data_group.values()).index(req[3])]

                    await User(req[0], call.from_user.id).remove_favourite_group(name_group)

                    await view_favourite_group(call, req[0]+"_favourite_remove")
                    await call.message.answer(f"Группа {name_group} была удалена из избранного!")

            elif req[2] == "n":
                await view_group(call, req[0]+"_f_a", int(req[3]))

            elif req[2] == "b":
                await view_group(call, req[0]+"_f_a", int(req[3])*-1)

        elif req[1] == "view":
            await view_schedule(call, req[2], int(req[3]), req[0])

        elif req[1] == "next":
            await view_next_back_schedule(call, req[2], req[3], req[0])

        elif req[1] == "settings":
            if req[2] == "main":
                await personal_settings_menu(call, req[0])
            else:
                data = (await User(req[0], call.from_user.id).get_data)[str(call.from_user.id)]
                temp = data['format_text']

                if req[2] == "name":
                    if temp['name'] == 1:
                        temp['name'] = 0
                    else:
                        temp['name'] = 1

                    await User(req[0], call.from_user.id).edit_data_user(data)
                    await personal_settings_menu(call, req[0])

                elif req[2] == "cabinet":
                    if temp['cabinet'] == 1:
                        temp['cabinet'] = 0
                    else:
                        temp['cabinet'] = 1

                    await User(req[0], call.from_user.id).edit_data_user(data)
                    await personal_settings_menu(call, req[0])

                elif req[2] == "teacher":
                    if temp['teacher'] == 1:
                        temp['teacher'] = 0
                    else:
                        temp['teacher'] = 1

                    await User(req[0], call.from_user.id).edit_data_user(data)
                    await personal_settings_menu(call, req[0])

                elif req[2] == "notification":
                    if data['get_notifications'] == 1:
                        data['get_notifications'] = 0
                    else:
                        data['get_notifications'] = 1

                    await User(req[0], call.from_user.id).edit_data_user(data)
                    await personal_settings_menu(call, req[0])

        elif req[1] == "search":
            if req[2] == "view":
                await period_schedule(call, req[0], req[3])

            elif req[2] == "add":
                data_group = (await StudentGroup().conversion_data)['Группы']
                name_group = list(data_group.keys())[list(data_group.values()).index(req[3])]

                await User(req[0], call.from_user.id).add_favourite_group(name_group, req[3])

                await call.message.answer(f"Группа {name_group} была добавлена в избранное!")

            elif req[2] == "main":
                await Form.name.set()
                await call.message.answer("Введите название группы(Вводить нужно как на сайте). Для отмены введите команду /cancel")

    # ------------------
    elif req[0] == "teacher":
        if req[1] == "menu":
            await markup_user(call, "teacher")

        elif req[1] == "schedule" or req[1] == "s":
            if req[2] == 'menu':
                await view_group(call, req[0]+"_s_g")

            elif req[2] == 'group' or req[2] == "g":
                await period_schedule(call, req[0], req[3])

            elif req[2] == "favourite":
                await view_favourite_group(call, req[0]+"_favourite_group")

            elif req[2] == "n":
                await view_group(call, req[0]+"_s_g", int(req[3]))
            elif req[2] == "b":
                await view_group(call, req[0] + "_s_g", int(req[3])*-1)

        elif req[1] == "view":
            await view_schedule(call, req[2], int(req[3]), req[0])

        elif req[1] == "next":
            await view_next_back_schedule(call, req[2], req[3], req[0])

        elif req[1] == "settings":
            if req[2] == "main":
                await personal_settings_menu(call, req[0])
            else:
                data = (await User(req[0], call.from_user.id).get_data)[str(call.from_user.id)]
                temp = data['format_text']

                if req[2] == "name":
                    if temp['name'] == 1:
                        temp['name'] = 0
                    else:
                        temp['name'] = 1

                    await User(req[0], call.from_user.id).edit_data_user(data)
                    await personal_settings_menu(call, req[0])

                elif req[2] == "cabinet":
                    if temp['cabinet'] == 1:
                        temp['cabinet'] = 0
                    else:
                        temp['cabinet'] = 1

                    await User(req[0], call.from_user.id).edit_data_user(data)
                    await personal_settings_menu(call, req[0])

                elif req[2] == "groups":
                    if temp['group'] == 1:
                        temp['group'] = 0
                    else:
                        temp['group'] = 1

                    await User(req[0], call.from_user.id).edit_data_user(data)
                    await personal_settings_menu(call, req[0])

                elif req[2] == "notification":
                    if data['get_notifications'] == 1:
                        data['get_notifications'] = 0
                    else:
                        data['get_notifications'] = 1

                    await User(req[0], call.from_user.id).edit_data_user(data)
                    await personal_settings_menu(call, req[0])

        elif req[1] == "favourite" or req[1] == "f":
            if req[2] == "view":
                if len(req) == 3:
                    await view_group(call, req[0] + "_f_a")
                elif len(req) == 5:
                    await view_schedule(call, req[3], int(req[4]), req[0])

            elif req[2] == "group":
                await period_schedule(call, req[0]+"_favourite", req[3])

            elif req[2] == "append" or req[2] == "a":
                data_group = (await TeacherGroup().conversion_data)['Группы']
                name_group = list(data_group.keys())[list(data_group.values()).index(req[3])]

                await User(req[0], call.from_user.id).add_favourite_group(name_group, req[3])
                await call.message.answer(f"{name_group} был(а) добавлен(а) в избранное!")

            elif req[2] == "remove":
                if (len(req) == 3):
                    await view_favourite_group(call, req[0] + "_favourite_remove")
                else:
                    data_group = (await TeacherGroup().conversion_data)['Группы']
                    name_group = list(data_group.keys())[list(data_group.values()).index(req[3])]

                    await User(req[0], call.from_user.id).remove_favourite_group(name_group)

                    await view_favourite_group(call, req[0] + "_favourite_remove")
                    await call.message.answer(f"{name_group} был(а) удален(а) из избранного!")

            elif req[2] == "n":
                await view_group(call, req[0]+"_f_a", int(req[3]))

            elif req[2] == "b":
                await view_group(call, req[0]+"_f_a", int(req[3])*-1)

        elif req[1] == "search":
            if req[2] == "view":
                await period_schedule(call, req[0], req[3])

            elif req[2] == "add":
                data_group = (await TeacherGroup().conversion_data)['Группы']
                name_group = list(data_group.keys())[list(data_group.values()).index(req[3])]

                await User(req[0], call.from_user.id).add_favourite_group(name_group, req[3])

                await call.message.answer(f"{name_group} был(а) добавлен(а) в избранное!")

            elif req[2] == "main":
                await Form.name.set()
                await call.message.answer("Введите ФИО(Вводить нужно как на сайте). Для отмены введите команду /cancel")

    # ---------------
    elif req[0] == "return":
        if req[1] == "main":
            await markup_menu(call.message, 1)

        elif req[1] == "student":
            if req[2] == 'menu':
                await markup_user(call, req[1])

            elif req[2] == "group":
                await view_group(call, req[1]+"_schedule_group")

            elif req[2] == "favourite":
                await view_favourite_group(call, req[1]+"_favourite_group")

        elif req[1] == "teacher":
            if req[2] == "menu":
                await markup_user(call, req[1])

            elif req[2] == "group":
                await view_group(call, req[1]+"_s_g")

            elif req[2] == "favourite":
                await view_favourite_group(call, req[1]+"_favourite_group")


@dp.message_handler(commands=['menu', 'start'])
async def menu(message: types.Message):
    await markup_menu(message)


async def check_change_schedule():
    print('Enable check change')
    data_name = await User("student").get_name_group_alert_enable

    if data_name is not None:
        count = 0
        for i in data_name:
            await StudentsSchedule(name_group=i, url=data_name[i]).check_change
            count += 1

            if count % 10 == 0:
                await asyncio.sleep(5)

        await asyncio.sleep(5)

    data_name = await User("teacher").get_name_group_alert_enable

    if data_name is not None:
        count = 0
        for i in data_name:
            await TeacherSchedule(name_group=i, url=data_name[i]).check_change
            count += 1

            if count % 10 == 0:
                await asyncio.sleep(5)


async def on_startup(_):
    scheduler = AsyncIOScheduler(timezone="Asia/Omsk")
    scheduler.add_job(check_change_schedule, trigger='cron', hour="7-21", day_of_week="mon-sun", minute="*/30")
    scheduler.start()


if __name__ == "__main__":
    try:
        executor.start_polling(dp, on_startup=on_startup)  # запуск бота
    except TerminatedByOtherGetUpdates:
        quit()

    # asyncio.run(test())
