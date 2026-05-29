# Tokki 환경 구성 진행 현황

작성일: 2026-04-29

## 개요

Tokki는 미국 옥수수/대두 그리드 셀에 대해 DSSAT 작물 시뮬레이션 모델을 대량으로 실행하는 Java 오케스트레이터입니다. 본 문서는 README 기반 환경 구성 진행 상황과 결과를 정리합니다.

## 작업 환경

- OS: WSL2 (Linux 6.6.87.2-microsoft-standard-WSL2)
- Java: 25.0.3 LTS
- 작업 위치: `~/codebase/Tokki` (WSL 홈)
  -원래 mnt 이용하여 C 드라이브에 접근/실행을 감행하려고 시도함
  - 빌드/실행 성능이 WSL 파일시스템이 유리함을 파악, WSL로 복귀

## 진행 단계

### 1. 사전 준비 도구 설치 (완료)

```bash
sudo apt install gfortran
sudo apt install maven
sudo apt install cmake
```

### 2. DSSAT 빌드 (완료)

```bash
mkdir ~/codebase
cd ~/codebase
git clone https://github.com/dssat/dssat-csm-os
cd dssat-csm-os
mkdir release && cd release
cmake -DCMAKE_BUILD_TYPE=RELEASE ..
make
```

결과물: `~/codebase/dssat-csm-os/release/bin/dscsm048`

### 3. Tokki 클론 (완료)

```bash
cd ~/codebase
git clone https://github.com/jawoo/Tokki
cd Tokki
```

### 4. DSSAT 리소스 복사 (완료)

```bash
cd ~/codebase/Tokki/res
cp ~/codebase/dssat-csm-os/Data/* ./.csm
cp ~/codebase/dssat-csm-os/Data/BatchFiles/* ./.csm
cp ~/codebase/dssat-csm-os/Data/Default/* ./.csm
cp ~/codebase/dssat-csm-os/Data/Genotype/* ./.csm
cp ~/codebase/dssat-csm-os/Data/Pest/* ./.csm
cp ~/codebase/dssat-csm-os/Data/StandardData/* ./.csm
cp ~/codebase/dssat-csm-os/release/bin/dscsm048 ./.csm/DSCSM048.EXE
```

### 5. 작업 디렉토리 생성 (완료)

```bash
mkdir ~/codebase/Tokki/res/result
cd ~/codebase/Tokki/res/.temp
mkdir summary flowering planting error
```

### 6. 날씨 데이터 배치 (완료)

SharePoint에서 `2021-2025_usa-mzsb-47707` 다운로드 후
`~/codebase/Tokki/res/weather/2021-2025_usa-mzsb-47707/`에 배치.

### 7. 프로젝트 빌드 (완료)

```bash
cd ~/codebase/Tokki
./mvnw clean package
```

결과: BUILD SUCCESS, `target/tokki-1.0-SNAPSHOT-jar-with-dependencies.jar` 생성.

### 8. 실행 테스트 (부분 성공)

```bash
java -jar target/tokki-1.0-SNAPSHOT-jar-with-dependencies.jar
```

**실행은 정상 완료됐으나 시뮬레이션이 0개**:

```
> Number of units to run: 0
> Found 0 planting dates.
> Done (00:00:12)
```

## 미완료 작업

### Cultivar 선택 (필수)

`res/.csm/MZCER048.CUL` 파일에서 사용할 품종 라인 끝에 ` *`를 추가해야 함.

**원인 분석**:
- `Utility.java:143 getCultivarCodes()`는 CUL 파일에서 `*` 플래그가 있는 라인만 품종으로 인식
- 플래그된 품종이 없으면 `cultivarList`가 비어 있어 unit 생성이 0개
- `App.java:226`의 `Number of units to run: 0`은 이 결과

**사용 가능한 품종 (총 168개)**:

| 코드 | 이름 | 비고 |
|---|---|---|
| `PC0001`~`PC0005` | 2500-2800 GDD | GDD 기반 |
| `990001` | LONG SEASON | 장기 |
| `990002` | MEDIUM SEASON | 중기 |
| `990003` | SHORT SEASON | 단기 |
| `IB0001`~ | 실제 품종 다수 | |

품종 선정은 연구 목적에 따라 결정 필요.

## 데이터 확인 결과

`res/input/unit-information_usa-mzsb-47707.csv`:
- 총 572,485 행
- `Crops`: MZ (옥수수)
- `PlantingDates`: 125 (DOY)
- 데이터 자체는 정상

## 참고 사항

- C 드라이브에 있던 기존 `/mnt/c/Users/ironm/dev/Tokki`는 작업 시작 전 일부 파일이 수정된 상태였으나, WSL 홈에서 새로 클론했으므로 영향 없음.
- C 드라이브 버전과 WSL 홈 버전의 `ScanningPlantingDates.java`는 줄바꿈(CRLF/LF) 차이만 있고 코드 내용은 동일.

## 다음 단계

1. `MZCER048.CUL`에서 사용할 품종 결정 후 `*` 플래그 추가
2. 재실행하여 unit 수와 시뮬레이션 결과 확인
3. 필요 시 `config.yml` 파라미터 조정 (시나리오 스위치, 비료/수분 옵션 등)
