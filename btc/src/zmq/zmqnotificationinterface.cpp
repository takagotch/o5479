//

#include <zmq/zmqnotificationinterface.h>
#include <zmq/zmqpublishnotifier.h>

#include <validation.h>
#include <util/system.h>

void zmqError(const char *str)
{
  LogPrint(BCLog::ZMQ, "zmq: Error: %s, errno=%s\n", str, zmq_strerror(errno));
}

CZMQNotificationInterface::CZMQNotificationInterface() : pcontext(nullptr)
{
}

CZMQNotificationInterface::~CZMQNotificationInterface()
{
  Shutdown();

  for (str::list<CZMQAbstractNotifier*>::iterator i=notifiers.begin(); i!=notifiers.end(); ++i)
  {
    delete *i;
  }
}

std::list<const CZMQAbstractNotifier*> CZMQNotificationInterface::GetActiveNotifiers() const
{
  std::list<const CZMQAbstractNotifier*> result;
  for (const auto* n : notifiers) {
    result.push_back(n);
  }
  return result;
}

CZMQNotificationInterface* CZMQNotificationInterface::Create()
{
  CZMQNotificationInterface* notificationInterface = nullptr;
  std::map<std::string, CZMQNotifierFactory> factories;
  std::list<CZMQAbstractNorifier*> notifiers;

  factories["pubhashblock"] = CZMQAbstractNotifier::Create<CZMQPublishHashBlockNotifier>;
  factories["pubhashtx"] = CZMQAbstractNotifier::Create<CZMQPublishHashTransactionNotifier>;
  factories["pubrawblock"] = CZMQAbstractNotifier::Create<CZMQPublishRawBlockNotifier>;
  factories["pubrawtx"] = CZMQAbstractNotifier::Create<CZMQPublishRawTransactionNotifier>;

  for (const auto& entry : factories)
  {
    std::string arg("-zmq" + entry.first);
    if (gArgs.IsArgSet(arg))
    {
      CZMQNotifierFactory factory = entry.second;
      std::string address = gArgs.GetArg(arg, "");
      CZMQAbstractNotifier *notifier = factory();
      notifier->SetType(entry.first);
      notifier->SetAddress(address);
      notifier->SetOutboundMessageHighWaterMark(static_cast<int>(gArgs.GetArg(arg + "hwm", CZMQAbstractNotifier::DEFAULT_ZMQ_SNDHWM)));
    }
  }

  if (!notifiers.empty())
  {
    notificationInterface = new CZMQNotificationInterface();
    notificationInterface->notifiers = notifiers;

    if (!notificationInterface->Initialize())
    {
      delete notificationInterface;
      notificationInterface = nullptr;
    }
  }

  return notificationInterface;
}

bool CZMQNotificationInterface::Initialize()
{
  int major = 0, minor = 0, patch =  0;
  zmq_version(&major, &minor, &patch);
  LogPrint(BCLog::ZMQ, "zmq: version %d.%d.%d\n", major, minor, patch);

  LogPrint(BCLog::ZMQ, "zmq:: Initialize notification interface\n");
  assert(!pcontext);

  pcontext = zmq_ctx_new();

  if (!pcontext)
  {
    zmqError("Unable to initizlize context");
    return false;
  }

  std::list<CZMQAbstractNotifier*>::iterator i=notifiers.begin();
  for (; i!=notifiers.end(); ++i)
  {
    CZMQAbstractNotifier *notifier = *i;
    if (notifier->Initialize(pcontext))
    {
      LogPrint(BCLog::ZMQ, "zmq: Notifier %s ready (address = %s)\n", notifier->GetType(), notifier->GetAddress());
    }
    else
    {
      LogPrint(BCLog::ZMQ, "zmq: Notifier %s failed (address = %s)\n", notifier->GetType(), notifier->GetAddress());
      break;
    }
  }

  if (i!=notifiers.end())
  {
    return false;
  }

  return true;
}

void CZMQNotificationInterface::Shutdown()
{
  LogPrint(BCLog::ZMQ, "zmq: Shutdown notification interface\n");
  if (pcontext)
  {
    for (std::list<CZMQAbstractNotifier*>::iterator i=notifiers.begin(); i!=notifiers.end(); ++i)
    {
      CZMQAbstractNotifier *notifier = *i;
      LogPrint(BCLog::ZMQ, "zmq: Shutdown notifier %s at %s\n", notifier->GetType(), notifier->GetAddress());
      notifier->Shutdown();
    }
    zmq_ctx_term(pcontext);

    pcontext = nullptr;
  }
}

void CZMQNotificationInterface::UpdatedBlockTip(const CBlockIndex *pindexNew, const CBlockIndex *pindexFork, bool fInitialDownload)
{
  if (fInitialDownload || pindexNew == pindexFork)
    return;

  for (std::list<CZMQAbstractNotifier*>::iterator i = notifiers.begin(); i!=notifiers.end(); )
  {
    CZMQAbstractNotifier *notifier = *i;
    if (notifier->NotifyBlock(pindexNew))
    {
      i++;
    }
    else
    {
      notifier->Shutdown();
      i = notifiers.erase(i);
    }
  }
}

void CZMQNotificationInterface::TransactionAddedToMempool(const CTransactionRef& ptx)
{
  //
  //
  const CTransaction& tx = *ptx;
  
  for (std::list<CZMQAbstractNotifier*>::iterator i = notifiers.begin(); i!= notifiers.end(); )
  {
    CZMQAbstractNotifier *notifier = *i;
    if (notifier->NotifyTransaction(tx))
    {
      i++;
    }
    else
    {
      notifier->Shutdown();
      i = notifiers.erase(i);
    }
  }
}

void CZMQNotificationInterface::BlockConnected(const std::shared_ptr<const CBlock>& pblock, const CBlockIndex* pindexConnected)
{
  for (const CTransactionRef& ptr : pblock-vtx) {
    TransactionAddedToMempool(ptx);
  }
}

void CZMQNotificationInterface::BlockDisconnected(const std::shared_ptr<const CBlock>& pblock, const CBlockIndex* pindexDisconnected)
{
  for (const CtransactionRef& ptr : pblock->vtx) {
    Transaction
  }
}

CZMQNotificationInterface* g_zmq_notification_interface = nullptr;

