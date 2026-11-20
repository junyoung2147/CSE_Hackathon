/**
 * 진로 프리셋:
 * 4학년 선택과목은 선수관계 데이터가 없는 경우가 많아서(화살표가 없음),
 * 도착점(targets)에 직접 넣어야 경로가 3학년에서 끊기지 않는다.
 * 진로마다 '도착점' 과목을 정해 두고,
 * 화면에서는 그 과목들 + 거기까지 가는 선수과목 전부를 경로로 보여준다.
 * 전공마다 같은 과목이 다른 코드일 수 있어서(예: 데이터베이스) 후보 코드를 모두 적고,
 * 선택한 전공 교육과정에 있는 것만 쓴다.
 */
export type Career = {
  id: string
  name: string
  description: string
  targets: string[]
}

export const careers: Career[] = [
  {
    id: 'ai',
    name: 'AI 엔지니어',
    description: '머신러닝·딥러닝 모델을 만들고 서비스에 붙이는 일',
    targets: ['ITEC0417', 'MOBI0224', 'ITEC0424', 'CAIB0211', 'CAIB0234', 'COMP0324', 'COMP0342', 'COMP0457', 'COMP0455'],
  },
  {
    id: 'system',
    name: '시스템·AI 인프라',
    description: 'OS·컴파일러·병렬처리 등 소프트웨어를 하드웨어 위에서 빠르게 돌리는 일',
    targets: ['COMP0312', 'COMP0321', 'ITEC0418', 'EECS0442', 'GLSO0227', 'COMP0411'],
  },
  {
    id: 'security',
    name: '보안·네트워크',
    description: '시스템과 네트워크를 공격으로부터 지키는 일',
    targets: ['COMP0341', 'COME0368', 'COMP0345', 'COMP0414', 'COMP0323', 'COMP0458', 'GLSO0227'],
  },
  {
    id: 'web',
    name: '웹·앱 서비스 개발',
    description: '사용자가 쓰는 웹·모바일 서비스를 설계하고 만드는 일',
    targets: ['ITEC0416', 'COME0427', 'COMP0322', 'COMP0422', 'COMP0328', 'COMP0420', 'ITEC0414', 'COMP0340', 'GLSO0227'],
  },
  {
    id: 'data',
    name: '데이터 사이언스',
    description: '데이터를 모으고 분석해서 의사결정에 쓰는 일',
    targets: ['ITEC0419', 'COMP0462', 'COME0427', 'COMP0322', 'ITEC0417', 'COMP0333', 'MBIO0402', 'GLSO0227'],
  },
]
