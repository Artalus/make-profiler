def easy():
    return \
r'''app.exe: file.o
	gcc -o app.exe file.o
appd.exe: filed.o
	GCC = gcc -g
	$(GCC) -o appd.exe filed.o
	echo "built debug"'''


def medium():
    return easy() + \
r'''

ifdef debug
build: appd.exe
else
build: app.exe
endif'''


def hard():
    return \
r'''all: build

export X=1
export Y=2

Z=3

app.exe: file.o
	gcc -o \
	app.exe \
	file.o
appd.exe: file.o
	gcc -o app.exe file.o

file.o: file.cpp
	gcc -c file.cpp -o file.o

ifdef debug
ifeq ($(debug),1)
build: appd.exe
else
build: app.exe
endif
else
build: appd.exe app.exe
endif

clean:
rm *.o
rm *.exe
#.PHONY : build'''